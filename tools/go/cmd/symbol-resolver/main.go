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

type Location struct {
	File   string `json:"file"`
	Line   int    `json:"line"`
	Column int    `json:"column"`
	Text   string `json:"text"`
}

type Symbol struct {
	Name       string     `json:"name"`
	Type       string     `json:"type"`
	Definition *Location  `json:"definition,omitempty"`
	References []Location `json:"references"`
}

type Result struct {
	Symbols    []Symbol `json:"symbols"`
	TotalRefs  int      `json:"total_refs"`
	FilesCount int      `json:"files_searched"`
	Error      string   `json:"error,omitempty"`
}

var defPatterns = map[string][]*regexp.Regexp{
	"python": {
		regexp.MustCompile(`^\s*def\s+(\w+)`),
		regexp.MustCompile(`^\s*class\s+(\w+)`),
	},
	"go": {
		regexp.MustCompile(`^func\s+(\w+)\s*\(`),
		regexp.MustCompile(`^func\s+\([^)]+\)\s+(\w+)\s*\(`),
		regexp.MustCompile(`^type\s+(\w+)`),
	},
	"javascript": {
		regexp.MustCompile(`^function\s+(\w+)`),
		regexp.MustCompile(`^class\s+(\w+)`),
		regexp.MustCompile(`^(?:const|let|var)\s+(\w+)\s*=`),
	},
}

func main() {
	symbolName := flag.String("symbol", "", "Symbol to find")
	dir := flag.String("dir", ".", "Directory")
	ext := flag.String("ext", "", "Extensions")
	flag.Parse()

	if *symbolName == "" {
		fmt.Fprintln(os.Stderr, "Error: -symbol required")
		os.Exit(1)
	}

	result := resolve(*symbolName, *dir, *ext)
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(result)
}

func resolve(name, dir, extensions string) Result {
	result := Result{Symbols: []Symbol{}}

	var extFilter map[string]bool
	if extensions != "" {
		extFilter = make(map[string]bool)
		for _, e := range strings.Split(extensions, ",") {
			e = strings.TrimSpace(e)
			if !strings.HasPrefix(e, ".") {
				e = "." + e
			}
			extFilter[e] = true
		}
	}

	var files []string
	filepath.Walk(dir, func(p string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			if info != nil && info.IsDir() {
				n := info.Name()
				if n != "." && (strings.HasPrefix(n, ".") || n == "node_modules" || n == "__pycache__") {
					return filepath.SkipDir
				}
			}
			return nil
		}
		ext := strings.ToLower(filepath.Ext(p))
		if extFilter != nil && !extFilter[ext] {
			return nil
		}
		if getLang(p) != "" {
			files = append(files, p)
		}
		return nil
	})

	result.FilesCount = len(files)

	type match struct {
		loc   Location
		isDef bool
	}

	workers := runtime.NumCPU()
	jobs := make(chan string, len(files))
	results := make(chan []match, len(files))
	var wg sync.WaitGroup

	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for f := range jobs {
				found := searchFile(f, name)
				var converted []match
				for _, m := range found {
					converted = append(converted, match{loc: m.loc, isDef: m.isDef})
				}
				results <- converted
			}
		}()
	}

	for _, f := range files {
		jobs <- f
	}
	close(jobs)

	go func() {
		wg.Wait()
		close(results)
	}()

	sym := Symbol{Name: name, References: []Location{}}
	for matches := range results {
		for _, m := range matches {
			if m.isDef && sym.Definition == nil {
				def := m.loc
				sym.Definition = &def
			} else {
				sym.References = append(sym.References, m.loc)
			}
		}
	}

	result.TotalRefs = len(sym.References)
	result.Symbols = append(result.Symbols, sym)
	return result
}

func getLang(p string) string {
	switch strings.ToLower(filepath.Ext(p)) {
	case ".py":
		return "python"
	case ".go":
		return "go"
	case ".js", ".jsx", ".ts", ".tsx":
		return "javascript"
	}
	return ""
}

func searchFile(path, name string) []struct {
	loc   Location
	isDef bool
} {
	var matches []struct {
		loc   Location
		isDef bool
	}

	file, err := os.Open(path)
	if err != nil {
		return matches
	}
	defer file.Close()

	lang := getLang(path)
	patterns := defPatterns[lang]
	refRe := regexp.MustCompile(`\b` + regexp.QuoteMeta(name) + `\b`)

	scanner := bufio.NewScanner(file)
	lineNum := 0

	for scanner.Scan() {
		lineNum++
		line := scanner.Text()

		isDef := false
		for _, p := range patterns {
			if m := p.FindStringSubmatch(line); m != nil && len(m) > 1 && m[1] == name {
				isDef = true
				break
			}
		}

		if isDef {
			matches = append(matches, struct {
				loc   Location
				isDef bool
			}{
				loc:   Location{File: path, Line: lineNum, Column: strings.Index(line, name) + 1, Text: strings.TrimSpace(line)},
				isDef: true,
			})
		} else if refRe.MatchString(line) {
			matches = append(matches, struct {
				loc   Location
				isDef bool
			}{
				loc:   Location{File: path, Line: lineNum, Column: strings.Index(line, name) + 1, Text: strings.TrimSpace(line)},
				isDef: false,
			})
		}
	}

	return matches
}
