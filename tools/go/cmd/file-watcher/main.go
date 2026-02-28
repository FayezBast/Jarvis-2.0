package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

type FileEvent struct {
	Type      string    `json:"type"`
	Path      string    `json:"path"`
	Timestamp time.Time `json:"timestamp"`
	Size      int64     `json:"size,omitempty"`
}

type FileState struct {
	ModTime time.Time `json:"mod_time"`
	Size    int64     `json:"size"`
}

type WatchResult struct {
	Success bool        `json:"success"`
	Events  []FileEvent `json:"events,omitempty"`
	Count   int         `json:"count"`
	Error   string      `json:"error,omitempty"`
}

type SnapshotResult struct {
	Success bool                 `json:"success"`
	Files   map[string]FileState `json:"files"`
	Count   int                  `json:"count"`
}

func main() {
	dir := flag.String("dir", ".", "Directory")
	ext := flag.String("ext", "", "Extensions")
	duration := flag.Int("duration", 0, "Watch seconds")
	exclude := flag.String("exclude", ".git,node_modules,__pycache__", "Exclude dirs")
	snapshot := flag.Bool("snapshot", false, "Snapshot only")
	since := flag.String("since", "", "Compare to snapshot file")
	flag.Parse()

	extFilter := parseExts(*ext)
	excludeMap := parseExclude(*exclude)

	if *snapshot {
		result := takeSnapshot(*dir, extFilter, excludeMap)
		outputJSON(result)
		return
	}

	if *since != "" {
		result := compareSnapshot(*dir, *since, extFilter, excludeMap)
		outputJSON(result)
		return
	}

	if *duration > 0 {
		result := watchFor(*dir, extFilter, excludeMap, *duration)
		outputJSON(result)
	} else {
		watchContinuous(*dir, extFilter, excludeMap)
	}
}

func outputJSON(v interface{}) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(v)
}

func parseExts(s string) map[string]bool {
	if s == "" {
		return nil
	}
	m := make(map[string]bool)
	for _, e := range strings.Split(s, ",") {
		e = strings.TrimSpace(e)
		if !strings.HasPrefix(e, ".") {
			e = "." + e
		}
		m[e] = true
	}
	return m
}

func parseExclude(s string) map[string]bool {
	m := make(map[string]bool)
	for _, d := range strings.Split(s, ",") {
		m[strings.TrimSpace(d)] = true
	}
	return m
}

func collectState(dir string, extFilter, excludeMap map[string]bool) map[string]FileState {
	state := make(map[string]FileState)
	filepath.Walk(dir, func(p string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if info.IsDir() {
			n := info.Name()
			if n != "." && (excludeMap[n] || strings.HasPrefix(n, ".")) {
				return filepath.SkipDir
			}
			return nil
		}
		if extFilter != nil {
			if !extFilter[strings.ToLower(filepath.Ext(p))] {
				return nil
			}
		}
		state[p] = FileState{ModTime: info.ModTime(), Size: info.Size()}
		return nil
	})
	return state
}

func takeSnapshot(dir string, extFilter, excludeMap map[string]bool) SnapshotResult {
	files := collectState(dir, extFilter, excludeMap)
	return SnapshotResult{Success: true, Files: files, Count: len(files)}
}

func compareSnapshot(dir, snapshotPath string, extFilter, excludeMap map[string]bool) WatchResult {
	data, err := os.ReadFile(snapshotPath)
	if err != nil {
		return WatchResult{Success: false, Error: err.Error()}
	}

	var old SnapshotResult
	if err := json.Unmarshal(data, &old); err != nil {
		return WatchResult{Success: false, Error: err.Error()}
	}

	current := collectState(dir, extFilter, excludeMap)
	events := compareStates(old.Files, current)

	return WatchResult{Success: true, Events: events, Count: len(events)}
}

func compareStates(old, new map[string]FileState) []FileEvent {
	var events []FileEvent
	now := time.Now()

	for p, os := range old {
		ns, ok := new[p]
		if !ok {
			events = append(events, FileEvent{Type: "deleted", Path: p, Timestamp: now})
		} else if ns.ModTime != os.ModTime {
			events = append(events, FileEvent{Type: "modified", Path: p, Timestamp: ns.ModTime, Size: ns.Size})
		}
	}

	for p, s := range new {
		if _, ok := old[p]; !ok {
			events = append(events, FileEvent{Type: "created", Path: p, Timestamp: s.ModTime, Size: s.Size})
		}
	}

	return events
}

func watchFor(dir string, extFilter, excludeMap map[string]bool, seconds int) WatchResult {
	state := collectState(dir, extFilter, excludeMap)
	var allEvents []FileEvent

	end := time.Now().Add(time.Duration(seconds) * time.Second)
	for time.Now().Before(end) {
		time.Sleep(time.Second)
		newState := collectState(dir, extFilter, excludeMap)
		events := compareStates(state, newState)
		allEvents = append(allEvents, events...)
		state = newState
	}

	return WatchResult{Success: true, Events: allEvents, Count: len(allEvents)}
}

func watchContinuous(dir string, extFilter, excludeMap map[string]bool) {
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	state := collectState(dir, extFilter, excludeMap)
	enc := json.NewEncoder(os.Stdout)

	fmt.Fprintf(os.Stderr, "Watching %s (Ctrl+C to stop)...\n", dir)

	for {
		select {
		case <-sig:
			return
		case <-time.After(time.Second):
			newState := collectState(dir, extFilter, excludeMap)
			for _, e := range compareStates(state, newState) {
				enc.Encode(e)
			}
			state = newState
		}
	}
}
