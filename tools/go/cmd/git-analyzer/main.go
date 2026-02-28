package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

type BlameInfo struct {
	Line   int    `json:"line"`
	Commit string `json:"commit"`
	Author string `json:"author"`
	Date   string `json:"date"`
	Text   string `json:"text"`
}

type CommitInfo struct {
	Hash    string `json:"hash"`
	Author  string `json:"author"`
	Date    string `json:"date"`
	Message string `json:"message"`
}

type FileChange struct {
	File   string `json:"file"`
	Status string `json:"status"`
}

type GitResult struct {
	Success  bool         `json:"success"`
	Mode     string       `json:"mode"`
	Blame    []BlameInfo  `json:"blame,omitempty"`
	Commits  []CommitInfo `json:"commits,omitempty"`
	Status   []FileChange `json:"status,omitempty"`
	Diff     string       `json:"diff,omitempty"`
	Branches []string     `json:"branches,omitempty"`
	Error    string       `json:"error,omitempty"`
}

func main() {
	mode := flag.String("mode", "", "blame, log, diff, status, branches")
	file := flag.String("file", "", "File path")
	commit := flag.String("commit", "", "Commit hash")
	count := flag.Int("count", 10, "Number of commits")
	since := flag.String("since", "", "Since date")
	repo := flag.String("repo", ".", "Repo path")
	flag.Parse()

	os.Chdir(*repo)

	var result GitResult
	result.Mode = *mode

	switch *mode {
	case "blame":
		result = getBlame(*file)
	case "log":
		result = getLog(*file, *count, *since)
	case "diff":
		result = getDiff(*commit, *file)
	case "status":
		result = getStatus()
	case "branches":
		result = getBranches()
	default:
		result.Error = "Mode required: blame, log, diff, status, branches"
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(result)
}

func runGit(args ...string) (string, error) {
	cmd := exec.Command("git", args...)
	out, err := cmd.Output()
	if err != nil {
		if e, ok := err.(*exec.ExitError); ok {
			return "", fmt.Errorf("%s", e.Stderr)
		}
		return "", err
	}
	return string(out), nil
}

func getBlame(file string) GitResult {
	if file == "" {
		return GitResult{Success: false, Error: "-file required"}
	}

	out, err := runGit("blame", "--line-porcelain", file)
	if err != nil {
		return GitResult{Success: false, Error: err.Error()}
	}

	var blames []BlameInfo
	lines := strings.Split(out, "\n")
	var cur BlameInfo
	lineNum := 0

	for _, l := range lines {
		if len(l) >= 40 && isHex(l[:40]) {
			if cur.Commit != "" {
				blames = append(blames, cur)
			}
			cur = BlameInfo{}
			parts := strings.Fields(l)
			cur.Commit = parts[0][:8]
			if len(parts) > 2 {
				lineNum, _ = strconv.Atoi(parts[2])
				cur.Line = lineNum
			}
		} else if strings.HasPrefix(l, "author ") {
			cur.Author = strings.TrimPrefix(l, "author ")
		} else if strings.HasPrefix(l, "author-time ") {
			ts, _ := strconv.ParseInt(strings.TrimPrefix(l, "author-time "), 10, 64)
			cur.Date = time.Unix(ts, 0).Format("2006-01-02")
		} else if strings.HasPrefix(l, "\t") {
			cur.Text = strings.TrimPrefix(l, "\t")
		}
	}
	if cur.Commit != "" {
		blames = append(blames, cur)
	}

	return GitResult{Success: true, Blame: blames}
}

func isHex(s string) bool {
	for _, c := range s {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
			return false
		}
	}
	return true
}

func getLog(file string, count int, since string) GitResult {
	args := []string{"log", fmt.Sprintf("-n%d", count), "--pretty=format:%H|%an|%aI|%s"}
	if since != "" {
		args = append(args, "--since", since)
	}
	if file != "" {
		args = append(args, "--", file)
	}

	out, err := runGit(args...)
	if err != nil {
		return GitResult{Success: false, Error: err.Error()}
	}

	var commits []CommitInfo
	for _, l := range strings.Split(strings.TrimSpace(out), "\n") {
		if l == "" {
			continue
		}
		parts := strings.SplitN(l, "|", 4)
		if len(parts) >= 4 {
			commits = append(commits, CommitInfo{
				Hash:    parts[0][:8],
				Author:  parts[1],
				Date:    parts[2][:10],
				Message: parts[3],
			})
		}
	}

	return GitResult{Success: true, Commits: commits}
}

func getDiff(commit, file string) GitResult {
	var args []string
	if commit != "" {
		args = []string{"diff", commit + "^", commit}
	} else {
		args = []string{"diff"}
	}
	if file != "" {
		args = append(args, "--", file)
	}

	out, err := runGit(args...)
	if err != nil {
		return GitResult{Success: false, Error: err.Error()}
	}
	return GitResult{Success: true, Diff: out}
}

func getStatus() GitResult {
	out, err := runGit("status", "--porcelain")
	if err != nil {
		return GitResult{Success: false, Error: err.Error()}
	}

	var changes []FileChange
	for _, l := range strings.Split(strings.TrimSpace(out), "\n") {
		if len(l) < 4 {
			continue
		}
		status := "modified"
		switch l[0] {
		case 'A':
			status = "added"
		case 'D':
			status = "deleted"
		case '?':
			status = "untracked"
		case 'M':
			status = "modified"
		}
		changes = append(changes, FileChange{File: strings.TrimSpace(l[3:]), Status: status})
	}
	return GitResult{Success: true, Status: changes}
}

func getBranches() GitResult {
	out, err := runGit("branch", "-a")
	if err != nil {
		return GitResult{Success: false, Error: err.Error()}
	}

	var branches []string
	for _, l := range strings.Split(strings.TrimSpace(out), "\n") {
		l = strings.TrimPrefix(l, "* ")
		l = strings.TrimSpace(l)
		if l != "" {
			branches = append(branches, l)
		}
	}
	return GitResult{Success: true, Branches: branches}
}
