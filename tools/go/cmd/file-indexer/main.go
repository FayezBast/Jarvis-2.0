// file-indexer - Fast parallel file indexing for Jarvis
// Scans directories and outputs file metadata as JSON
package main

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

type FileInfo struct {
	Path      string    `json:"path"`
	Name      string    `json:"name"`
	Size      int64     `json:"size"`
	Extension string    `json:"extension"`
	Modified  time.Time `json:"modified"`
	IsDir     bool      `json:"is_dir"`
	Hash      string    `json:"hash,omitempty"`
}

type IndexResult struct {
	Files      []FileInfo `json:"files"`
	TotalFiles int        `json:"total_files"`
	TotalSize  int64      `json:"total_size"`
	Duration   string     `json:"duration"`
	Error      string     `json:"error,omitempty"`
}

type IndexJob struct {
	Path string
	Info os.FileInfo
}

func main() {
	dir := flag.String("dir", ".", "Directory to index")
	withHash := flag.Bool("hash", false, "Calculate MD5 hash for each file")
	extensions := flag.String("ext", "", "Filter by extensions (comma-separated, e.g., 'py,go,js')")
	maxDepth := flag.Int("depth", -1, "Maximum directory depth (-1 for unlimited)")
	excludeDirs := flag.String("exclude", ".git,node_modules,__pycache__,vendor,.venv,venv", "Directories to exclude (comma-separated)")
	flag.Parse()

	start := time.Now()
	result := indexDirectory(*dir, *withHash, *extensions, *maxDepth, *excludeDirs)
	result.Duration = time.Since(start).String()

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(result)
}

func indexDirectory(dir string, withHash bool, extensions string, maxDepth int, excludeDirs string) IndexResult {
	result := IndexResult{Files: []FileInfo{}}

	// Parse extensions filter
	var extFilter map[string]bool
	if extensions != "" {
		extFilter = make(map[string]bool)
		for _, ext := range strings.Split(extensions, ",") {
			ext = strings.TrimSpace(ext)
			if !strings.HasPrefix(ext, ".") {
				ext = "." + ext
			}
			extFilter[strings.ToLower(ext)] = true
		}
	}

	// Parse exclude dirs
	excludeMap := make(map[string]bool)
	for _, d := range strings.Split(excludeDirs, ",") {
		excludeMap[strings.TrimSpace(d)] = true
	}

	baseDepth := strings.Count(filepath.Clean(dir), string(os.PathSeparator))

	// Collect all files first
	var jobs []IndexJob
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}

		// Check depth
		if maxDepth >= 0 {
			currentDepth := strings.Count(filepath.Clean(path), string(os.PathSeparator)) - baseDepth
			if currentDepth > maxDepth {
				if info.IsDir() {
					return filepath.SkipDir
				}
				return nil
			}
		}

		// Skip excluded directories (but not the root ".")
		if info.IsDir() {
			name := info.Name()
			if name != "." && (excludeMap[name] || strings.HasPrefix(name, ".")) {
				return filepath.SkipDir
			}
			return nil
		}

		// Filter by extension
		if extFilter != nil {
			ext := strings.ToLower(filepath.Ext(path))
			if !extFilter[ext] {
				return nil
			}
		}

		jobs = append(jobs, IndexJob{Path: path, Info: info})
		return nil
	})

	if err != nil {
		result.Error = fmt.Sprintf("Walk error: %v", err)
		return result
	}

	// Process files in parallel
	numWorkers := runtime.NumCPU()
	jobChan := make(chan IndexJob, len(jobs))
	resultChan := make(chan FileInfo, len(jobs))
	var wg sync.WaitGroup

	// Start workers
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobChan {
				fi := processFile(job, withHash)
				resultChan <- fi
			}
		}()
	}

	// Send jobs
	for _, job := range jobs {
		jobChan <- job
	}
	close(jobChan)

	// Wait and close results
	go func() {
		wg.Wait()
		close(resultChan)
	}()

	// Collect results
	for fi := range resultChan {
		result.Files = append(result.Files, fi)
		result.TotalSize += fi.Size
	}

	result.TotalFiles = len(result.Files)
	return result
}

func processFile(job IndexJob, withHash bool) FileInfo {
	fi := FileInfo{
		Path:      job.Path,
		Name:      job.Info.Name(),
		Size:      job.Info.Size(),
		Extension: filepath.Ext(job.Path),
		Modified:  job.Info.ModTime(),
		IsDir:     job.Info.IsDir(),
	}

	if withHash && !job.Info.IsDir() && job.Info.Size() < 10*1024*1024 {
		if hash, err := hashFile(job.Path); err == nil {
			fi.Hash = hash
		}
	}

	return fi
}

func hashFile(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()

	hash := md5.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}

	return hex.EncodeToString(hash.Sum(nil)), nil
}
