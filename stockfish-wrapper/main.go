package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/coder/websocket"
)

const maxClientFrameBytes = 4096

var (
	stockfishPath string

	activeSessions atomic.Int64
	totalSessions  atomic.Int64
	killCount      atomic.Int64

	healthMu      sync.RWMutex
	healthVersion string
	healthOk      bool
)

func main() {
	port := flag.String("port", "8082", "port to listen on")
	flag.StringVar(&stockfishPath, "binary", "/usr/local/bin/stockfish", "path to stockfish binary")
	flag.Parse()

	probeStockfishVersion()

	mux := http.NewServeMux()
	mux.HandleFunc("/stockfish/health", handleHealth)
	mux.HandleFunc("/stockfish/metrics", handleMetrics)
	mux.HandleFunc("/stockfish/uci", handleUCIWebSocket)

	addr := ":" + *port
	log.Printf("stockfish-http-wrapper listening on %s (binary=%s)", addr, stockfishPath)
	log.Fatal(http.ListenAndServe(addr, mux))
}

func probeStockfishVersion() {
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, stockfishPath)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		setHealth(false, fmt.Sprintf("stdin: %v", err))
		return
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		setHealth(false, fmt.Sprintf("stdout: %v", err))
		return
	}
	if err := cmd.Start(); err != nil {
		setHealth(false, fmt.Sprintf("start: %v", err))
		return
	}

	_, _ = fmt.Fprintln(stdin, "uci")
	sc := bufio.NewScanner(stdout)
	sc.Buffer(make([]byte, 0, 4096), 1024*1024)
	found := ""
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "id name ") {
			found = strings.TrimPrefix(line, "id name ")
			break
		}
	}
	_, _ = fmt.Fprintln(stdin, "quit")
	_ = stdin.Close()
	_ = cmd.Wait()

	if found != "" {
		setHealth(true, found)
		return
	}
	setHealth(false, "uci handshake missing id name")
}

func setHealth(ok bool, version string) {
	healthMu.Lock()
	defer healthMu.Unlock()
	healthOk = ok
	healthVersion = version
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, `{"error":"GET required"}`, http.StatusMethodNotAllowed)
		return
	}
	healthMu.RLock()
	ok := healthOk
	ver := healthVersion
	healthMu.RUnlock()
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"ok":      ok,
		"version": ver,
	})
}

func handleMetrics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "GET required", http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = fmt.Fprintf(w, "stockfish_wrapper_active_sessions %d\n", activeSessions.Load())
	_, _ = fmt.Fprintf(w, "stockfish_wrapper_total_sessions %d\n", totalSessions.Load())
	_, _ = fmt.Fprintf(w, "stockfish_wrapper_kill_count %d\n", killCount.Load())
}

func handleUCIWebSocket(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	c, err := websocket.Accept(w, r, &websocket.AcceptOptions{
		OriginPatterns:  []string{"*"},
		CompressionMode: websocket.CompressionDisabled,
	})
	if err != nil {
		log.Printf("websocket accept failed: %v", err)
		return
	}
	defer func() {
		_ = c.Close(websocket.StatusNormalClosure, "done")
	}()

	totalSessions.Add(1)
	activeSessions.Add(1)
	defer activeSessions.Add(-1)

	cmd := exec.Command(stockfishPath)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		_ = c.Close(websocket.StatusInternalError, "stdin pipe")
		return
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		_ = c.Close(websocket.StatusInternalError, "stdout pipe")
		return
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		_ = c.Close(websocket.StatusInternalError, "stderr pipe")
		return
	}

	if err := cmd.Start(); err != nil {
		_ = c.Close(websocket.StatusInternalError, "engine start")
		return
	}

	var wg sync.WaitGroup
	wg.Add(2)

	go func() {
		defer wg.Done()
		sc := bufio.NewScanner(stdout)
		sc.Buffer(make([]byte, 0, 8192), 4*1024*1024)
		for sc.Scan() {
			line := sc.Text()
			ctxW, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			werr := c.Write(ctxW, websocket.MessageText, []byte(line))
			cancel()
			if werr != nil {
				return
			}
		}
	}()

	go func() {
		defer wg.Done()
		sc := bufio.NewScanner(stderr)
		for sc.Scan() {
			line := "! " + sc.Text()
			ctxW, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			werr := c.Write(ctxW, websocket.MessageText, []byte(line))
			cancel()
			if werr != nil {
				return
			}
		}
	}()

	go func() {
		<-ctx.Done()
		_, _ = stdin.Write([]byte("quit\n"))
	}()

readLoop:
	for {
		typ, data, rerr := c.Read(ctx)
		if rerr != nil {
			break readLoop
		}
		if typ != websocket.MessageText {
			continue
		}
		if len(data) > maxClientFrameBytes {
			killCount.Add(1)
			break readLoop
		}
		payload := string(data)
		lines := strings.Split(strings.ReplaceAll(payload, "\r\n", "\n"), "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" {
				continue
			}
			if len(line) > maxClientFrameBytes {
				killCount.Add(1)
				break readLoop
			}
			if _, werr := stdin.Write([]byte(line + "\n")); werr != nil {
				break readLoop
			}
		}
	}

	_, _ = stdin.Write([]byte("quit\n"))
	_ = stdin.Close()

	waitDone := make(chan struct{})
	go func() {
		_ = cmd.Wait()
		close(waitDone)
	}()

	select {
	case <-waitDone:
	case <-time.After(2 * time.Second):
		if cmd.Process != nil {
			_ = cmd.Process.Kill()
			killCount.Add(1)
		}
		<-waitDone
	}

	wg.Wait()
}
