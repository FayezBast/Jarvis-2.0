package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
)

type DiffHunk struct {
	OldStart int      `json:"old_start"`
	OldCount int      `json:"old_count"`
	NewStart int      `json:"new_start"`
	NewCount int      `json:"new_count"`
	Lines    []string `json:"lines"`
}

type FileDiff struct {
	OldFile string     `json:"old_file"`
	NewFile string     `json:"new_file"`
	Hunks   []DiffHunk `json:"hunks"`
}

type DiffResult struct {
	Success bool     `json:"success"`
	Diff    FileDiff `json:"diff,omitempty"`
	Patch   string   `json:"patch,omitempty"`
	Error   string   `json:"error,omitempty"`
}

type ApplyResult struct {
	Success  bool   `json:"success"`
	FilePath string `json:"file_path"`
	Content  string `json:"content,omitempty"`
	Error    string `json:"error,omitempty"`
}

func main() {
	mode := flag.String("mode", "diff", "Mode: diff, apply, preview")
	oldFile := flag.String("old", "", "Old file path")
	newFile := flag.String("new", "", "New file path")
	targetFile := flag.String("target", "", "Target file")
	oldText := flag.String("old-text", "", "Old text to replace")
	newText := flag.String("new-text", "", "New text")
	context := flag.Int("context", 3, "Context lines")
	flag.Parse()

	switch *mode {
	case "diff":
		if *oldFile != "" && *newFile != "" {
			result := generateDiff(*oldFile, *newFile, *context)
			outputJSON(result)
		} else {
			outputJSON(DiffResult{Success: false, Error: "-old and -new required"})
		}
	case "apply":
		if *targetFile != "" && *oldText != "" {
			result := applyReplace(*targetFile, *oldText, *newText, false)
			outputJSON(result)
		} else {
			outputJSON(ApplyResult{Success: false, Error: "-target and -old-text required"})
		}
	case "preview":
		if *targetFile != "" && *oldText != "" {
			result := applyReplace(*targetFile, *oldText, *newText, true)
			outputJSON(result)
		} else {
			outputJSON(ApplyResult{Success: false, Error: "-target and -old-text required"})
		}
	}
}

func outputJSON(v interface{}) {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(v)
}

func readLines(path string) ([]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	var lines []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	return lines, scanner.Err()
}

func generateDiff(oldPath, newPath string, contextLines int) DiffResult {
	oldLines, err := readLines(oldPath)
	if err != nil {
		return DiffResult{Success: false, Error: err.Error()}
	}
	newLines, err := readLines(newPath)
	if err != nil {
		return DiffResult{Success: false, Error: err.Error()}
	}

	hunks := computeDiff(oldLines, newLines, contextLines)
	patch := generatePatch(oldPath, newPath, hunks)

	return DiffResult{
		Success: true,
		Diff:    FileDiff{OldFile: oldPath, NewFile: newPath, Hunks: hunks},
		Patch:   patch,
	}
}

func computeDiff(old, new []string, ctx int) []DiffHunk {
	var hunks []DiffHunk
	i, j := 0, 0

	for i < len(old) || j < len(new) {
		for i < len(old) && j < len(new) && old[i] == new[j] {
			i++
			j++
		}
		if i >= len(old) && j >= len(new) {
			break
		}

		start := max(0, i-ctx)
		var lines []string

		for k := start; k < i; k++ {
			lines = append(lines, " "+old[k])
		}

		for i < len(old) || j < len(new) {
			if i < len(old) && j < len(new) && old[i] == new[j] {
				match := 0
				for k := 0; i+k < len(old) && j+k < len(new) && old[i+k] == new[j+k]; k++ {
					match++
				}
				if match > ctx*2 {
					for k := 0; k < ctx && i < len(old); k++ {
						lines = append(lines, " "+old[i])
						i++
						j++
					}
					break
				}
				lines = append(lines, " "+old[i])
				i++
				j++
			} else if i < len(old) {
				lines = append(lines, "-"+old[i])
				i++
			} else if j < len(new) {
				lines = append(lines, "+"+new[j])
				j++
			}
		}

		if len(lines) > 0 {
			hunks = append(hunks, DiffHunk{
				OldStart: start + 1,
				OldCount: i - start,
				NewStart: start + 1,
				NewCount: j - start,
				Lines:    lines,
			})
		}
	}
	return hunks
}

func generatePatch(oldPath, newPath string, hunks []DiffHunk) string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("--- %s\n+++ %s\n", oldPath, newPath))
	for _, h := range hunks {
		sb.WriteString(fmt.Sprintf("@@ -%d,%d +%d,%d @@\n", h.OldStart, h.OldCount, h.NewStart, h.NewCount))
		for _, l := range h.Lines {
			sb.WriteString(l + "\n")
		}
	}
	return sb.String()
}

func applyReplace(path, oldText, newText string, preview bool) ApplyResult {
	content, err := os.ReadFile(path)
	if err != nil {
		return ApplyResult{Success: false, Error: err.Error()}
	}

	s := string(content)
	if !strings.Contains(s, oldText) {
		return ApplyResult{Success: false, Error: "Text not found"}
	}

	count := strings.Count(s, oldText)
	if count > 1 {
		return ApplyResult{Success: false, Error: fmt.Sprintf("Found %d matches, need unique match", count)}
	}

	newContent := strings.Replace(s, oldText, newText, 1)

	if preview {
		return ApplyResult{Success: true, FilePath: path, Content: newContent}
	}

	if err := os.WriteFile(path, []byte(newContent), 0644); err != nil {
		return ApplyResult{Success: false, Error: err.Error()}
	}
	return ApplyResult{Success: true, FilePath: path}
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
