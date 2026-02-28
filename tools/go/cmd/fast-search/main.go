// fast-search - A high-performance file search tool for Jarvis
// Searches files in parallel using goroutines for maximum speed
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
)

type Match struct {
	File    string `json:"file"`
	Line    int    `json:"line"`
	Content string `json:"content"`
}

type Result struct {
	Matches []Match `json:"matches"`
	Count   int     `json:"count"`
	Error   string  `json:"error,omitempty"`
}

type SearchJob struct {
	Path string
}

func main() {
	// Parse flags
	pattern := flag.String("pattern", "", "Search pattern (string or regex)")
	dir := flag.String("dir", ".", "Directory to search")
	regex := flag.Bool("regex", false, "Treat pattern as regex")
	ignoreCase := flag.Bool("i", false, "Case insensitive search")
	filePattern := flag.String("files", "", "File glob pattern (e.g., '*.py')")
	maxResults := flag.Int("max", 100, "Maximum number of results")
	jsonOutput := flag.Bool("json", false, "Output as JSON")
	flag.Parse()

	if *pattern == "" {
		fmt.Fprintln(os.Stderr, "Error: -pattern is required")
		os.Exit(1)
	}

	result := search(*dir, *pattern, *regex, *ignoreCase, *filePattern, *maxResults)

	if *jsonOutput {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		enc.Encode(result)
	} else {
		for _, m := range result.Matches {
			fmt.Printf("%s:%d: %s\n", m.File, m.Line, strings.TrimSpace(m.Content))
		}
		if result.Error != "" {
			fmt.Fprintf(os.Stderr, "Error: %s\n", result.Error)
		}
	}
}

func search(dir, pattern string, isRegex, ignoreCase bool, filePattern string, maxResults int) Result {
	result := Result{Matches: []Match{}}

	// Compile pattern
	var re *regexp.Regexp
	var searchStr string
	var err error

	if isRegex {
		if ignoreCase {
			pattern = "(?i)" + pattern
		}
		re, err = regexp.Compile(pattern)
		if err != nil {
			result.Error = fmt.Sprintf("Invalid regex: %v", err)
			return result
		}
	} else {
		searchStr = pattern
		if ignoreCase {
			searchStr = strings.ToLower(pattern)
		}
	}

	// Collect files to search
	var files []string
	err = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Skip errors
		}

		// Skip hidden directories and common non-code dirs (but not the root ".")
		if info.IsDir() {
			name := info.Name()
			if name != "." && (strings.HasPrefix(name, ".") || name == "node_modules" || name == "__pycache__" || name == "vendor" || name == "target") {
				return filepath.SkipDir
			}
			return nil
		}

		// Check file pattern
		if filePattern != "" {
			matched, _ := filepath.Match(filePattern, info.Name())
			if !matched {
				return nil
			}
		}

		// Skip binary files (basic check)
		ext := strings.ToLower(filepath.Ext(path))
		binaryExts := map[string]bool{".exe": true, ".bin": true, ".so": true, ".dylib": true, ".dll": true, ".o": true, ".a": true, ".pyc": true, ".class": true, ".jar": true, ".zip": true, ".tar": true, ".gz": true, ".png": true, ".jpg": true, ".jpeg": true, ".gif": true, ".pdf": true, ".mp3": true, ".mp4": true}
		if binaryExts[ext] {
			return nil
		}

		files = append(files, path)
		return nil
	})

	if err != nil {
		result.Error = fmt.Sprintf("Walk error: %v", err)
		return result
	}

	// Search files in parallel
	numWorkers := runtime.NumCPU()
	jobs := make(chan SearchJob, len(files))
	results := make(chan []Match, len(files))
	var wg sync.WaitGroup

	// Start workers
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				matches := searchFile(job.Path, re, searchStr, ignoreCase, isRegex)
				results <- matches
			}
		}()
	}

	// Send jobs
	for _, f := range files {
		jobs <- SearchJob{Path: f}
	}
	close(jobs)

	// Collect results in background
	go func() {
		wg.Wait()
		close(results)
	}()

	// Gather matches
	for matches := range results {
		for _, m := range matches {
			if len(result.Matches) >= maxResults {
				break
			}
			result.Matches = append(result.Matches, m)
		}
		if len(result.Matches) >= maxResults {
			break
		}
	}

	result.Count = len(result.Matches)
	return result
}

func searchFile(path string, re *regexp.Regexp, searchStr string, ignoreCase, isRegex bool) []Match {
	var matches []Match

	file, err := os.Open(path)
	if err != nil {
		return matches
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	lineNum := 0

	for scanner.Scan() {
		lineNum++
		line := scanner.Text()
		var found bool

		if isRegex {
			found = re.MatchString(line)
		} else {
			if ignoreCase {
				found = strings.Contains(strings.ToLower(line), searchStr)
			} else {
				found = strings.Contains(line, searchStr)
			}
		}

		if found {
			matches = append(matches, Match{
				File:    path,
				Line:    lineNum,
				Content: line,
			})
		}
	}

	return matches
}
