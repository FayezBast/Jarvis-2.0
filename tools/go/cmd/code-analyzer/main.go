// code-analyzer - Fast code structure analysis for Jarvis
// Parses source files and extracts functions, classes, imports, etc.
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

type Symbol struct {
	Name       string   `json:"name"`
	Type       string   `json:"type"`
	Line       int      `json:"line"`
	EndLine    int      `json:"end_line,omitempty"`
	Signature  string   `json:"signature,omitempty"`
	DocString  string   `json:"docstring,omitempty"`
	Parent     string   `json:"parent,omitempty"`
	Decorators []string `json:"decorators,omitempty"`
}

type FileAnalysis struct {
	Path      string   `json:"path"`
	Language  string   `json:"language"`
	Symbols   []Symbol `json:"symbols"`
	Imports   []string `json:"imports"`
	LineCount int      `json:"line_count"`
	Error     string   `json:"error,omitempty"`
}

type AnalysisResult struct {
	Files      []FileAnalysis `json:"files"`
	TotalFiles int            `json:"total_files"`
	Duration   string         `json:"duration,omitempty"`
	Error      string         `json:"error,omitempty"`
}

type LanguagePatterns struct {
	Function  *regexp.Regexp
	Class     *regexp.Regexp
	Method    *regexp.Regexp
	Import    *regexp.Regexp
	Decorator *regexp.Regexp
	DocString *regexp.Regexp
	Variable  *regexp.Regexp
}

var languagePatterns = map[string]*LanguagePatterns{
	"python": {
		Function:  regexp.MustCompile(`^(\s*)def\s+(\w+)\s*\((.*?)\).*?:`),
		Class:     regexp.MustCompile(`^(\s*)class\s+(\w+)(?:\s*\((.*?)\))?\s*:`),
		Import:    regexp.MustCompile(`^(?:from\s+(\S+)\s+)?import\s+(.+)`),
		Decorator: regexp.MustCompile(`^(\s*)@(\w+(?:\.\w+)*(?:\(.*?\))?)`),
	},
	"go": {
		Function: regexp.MustCompile(`^func\s+(?:\((\w+)\s+\*?(\w+)\)\s+)?(\w+)\s*\((.*?)\)`),
		Import:   regexp.MustCompile(`^\s*(?:import\s+)?(?:"([^"]+)"|(\w+)\s+"([^"]+)")`),
	},
	"javascript": {
		Function: regexp.MustCompile(`^(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\(.*?\)\s*=>))`),
		Class:    regexp.MustCompile(`^class\s+(\w+)(?:\s+extends\s+(\w+))?`),
		Import:   regexp.MustCompile(`^import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+['"]([^'"]+)['"]`),
	},
	"typescript": {
		Function: regexp.MustCompile(`^(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?(?:function|\(.*?\)\s*=>))`),
		Class:    regexp.MustCompile(`^(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?`),
		Import:   regexp.MustCompile(`^import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+['"]([^'"]+)['"]`),
	},
}

func main() {
	path := flag.String("path", "", "File or directory to analyze")
	extensions := flag.String("ext", "", "Filter by extensions (comma-separated)")
	symbolType := flag.String("type", "", "Filter by symbol type (function, class, import)")
	maxDepth := flag.Int("depth", -1, "Maximum directory depth (-1 for unlimited)")
	flag.Parse()

	if *path == "" {
		fmt.Fprintln(os.Stderr, "Error: -path is required")
		os.Exit(1)
	}

	result := analyze(*path, *extensions, *symbolType, *maxDepth)

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(result)
}

func analyze(path, extensions, symbolType string, maxDepth int) AnalysisResult {
	result := AnalysisResult{Files: []FileAnalysis{}}

	info, err := os.Stat(path)
	if err != nil {
		result.Error = fmt.Sprintf("Cannot access path: %v", err)
		return result
	}

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

	var files []string
	if info.IsDir() {
		baseDepth := strings.Count(filepath.Clean(path), string(os.PathSeparator))
		filepath.Walk(path, func(p string, info os.FileInfo, err error) error {
			if err != nil {
				return nil
			}

			if info.IsDir() {
				name := info.Name()
				if name != "." && (strings.HasPrefix(name, ".") || name == "node_modules" || name == "__pycache__" || name == "vendor") {
					return filepath.SkipDir
				}
				if maxDepth >= 0 {
					currentDepth := strings.Count(filepath.Clean(p), string(os.PathSeparator)) - baseDepth
					if currentDepth > maxDepth {
						return filepath.SkipDir
					}
				}
				return nil
			}

			ext := strings.ToLower(filepath.Ext(p))
			if extFilter != nil && !extFilter[ext] {
				return nil
			}

			if getLanguage(p) != "" {
				files = append(files, p)
			}
			return nil
		})
	} else {
		files = append(files, path)
	}

	numWorkers := runtime.NumCPU()
	jobs := make(chan string, len(files))
	results := make(chan FileAnalysis, len(files))
	var wg sync.WaitGroup

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for filePath := range jobs {
				analysis := analyzeFile(filePath, symbolType)
				results <- analysis
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

	for analysis := range results {
		result.Files = append(result.Files, analysis)
	}

	result.TotalFiles = len(result.Files)
	return result
}

func getLanguage(path string) string {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case ".py":
		return "python"
	case ".go":
		return "go"
	case ".js", ".jsx", ".mjs":
		return "javascript"
	case ".ts", ".tsx":
		return "typescript"
	default:
		return ""
	}
}

func analyzeFile(path, symbolTypeFilter string) FileAnalysis {
	analysis := FileAnalysis{
		Path:     path,
		Language: getLanguage(path),
		Symbols:  []Symbol{},
		Imports:  []string{},
	}

	file, err := os.Open(path)
	if err != nil {
		analysis.Error = err.Error()
		return analysis
	}
	defer file.Close()

	patterns := languagePatterns[analysis.Language]
	if patterns == nil {
		return analysis
	}

	scanner := bufio.NewScanner(file)
	lineNum := 0
	var currentClass string
	var pendingDecorators []string
	var inMultilineImport bool
	var importBuffer string

	for scanner.Scan() {
		lineNum++
		line := scanner.Text()
		trimmedLine := strings.TrimSpace(line)

		if trimmedLine == "" {
			continue
		}

		if inMultilineImport {
			importBuffer += " " + trimmedLine
			if strings.Contains(trimmedLine, ")") {
				inMultilineImport = false
				analysis.Imports = append(analysis.Imports, strings.TrimSpace(importBuffer))
				importBuffer = ""
			}
			continue
		}

		if patterns.Decorator != nil {
			if matches := patterns.Decorator.FindStringSubmatch(line); matches != nil {
				pendingDecorators = append(pendingDecorators, matches[2])
				continue
			}
		}

		if patterns.Import != nil {
			if matches := patterns.Import.FindStringSubmatch(line); matches != nil {
				importStr := trimmedLine
				if strings.Contains(line, "(") && !strings.Contains(line, ")") {
					inMultilineImport = true
					importBuffer = trimmedLine
					continue
				}
				analysis.Imports = append(analysis.Imports, importStr)

				if symbolTypeFilter == "" || symbolTypeFilter == "import" {
					symbol := Symbol{
						Name: importStr,
						Type: "import",
						Line: lineNum,
					}
					analysis.Symbols = append(analysis.Symbols, symbol)
				}
				continue
			}
		}

		if patterns.Class != nil {
			if matches := patterns.Class.FindStringSubmatch(line); matches != nil {
				indent := 0
				if len(matches) > 1 {
					indent = len(matches[1])
				}
				className := matches[2]
				if analysis.Language == "javascript" || analysis.Language == "typescript" {
					className = matches[1]
				}
				if indent == 0 {
					currentClass = className
				}

				if symbolTypeFilter == "" || symbolTypeFilter == "class" {
					symbol := Symbol{
						Name:       className,
						Type:       "class",
						Line:       lineNum,
						Decorators: pendingDecorators,
					}
					analysis.Symbols = append(analysis.Symbols, symbol)
				}
				pendingDecorators = nil
				continue
			}
		}

		if patterns.Function != nil {
			if matches := patterns.Function.FindStringSubmatch(line); matches != nil {
				var name, signature string
				var isMethod bool

				if analysis.Language == "python" {
					indent := len(matches[1])
					name = matches[2]
					signature = matches[3]
					isMethod = indent > 0 && currentClass != ""
				} else if analysis.Language == "go" {
					if matches[1] != "" {
						name = matches[3]
						signature = matches[4]
						isMethod = true
						currentClass = matches[2]
					} else {
						name = matches[3]
						signature = matches[4]
					}
				} else {
					if matches[1] != "" {
						name = matches[1]
					} else {
						name = matches[2]
					}
				}

				symType := "function"
				if isMethod {
					symType = "method"
				}

				if symbolTypeFilter == "" || symbolTypeFilter == symType {
					symbol := Symbol{
						Name:       name,
						Type:       symType,
						Line:       lineNum,
						Signature:  signature,
						Decorators: pendingDecorators,
					}
					if isMethod {
						symbol.Parent = currentClass
					}
					analysis.Symbols = append(analysis.Symbols, symbol)
				}
				pendingDecorators = nil
				continue
			}
		}

		if len(pendingDecorators) > 0 && !strings.HasPrefix(trimmedLine, "@") {
			pendingDecorators = nil
		}

		if analysis.Language == "python" && currentClass != "" {
			if len(line) > 0 && line[0] != ' ' && line[0] != '\t' && !strings.HasPrefix(trimmedLine, "#") {
				currentClass = ""
			}
		}
	}

	analysis.LineCount = lineNum
	return analysis
}
