// parallel-runner - Execute multiple commands in parallel
// Runs tasks concurrently and collects results
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"
)

type Task struct {
	ID      string `json:"id"`
	Command string `json:"command"`
	Dir     string `json:"dir,omitempty"`
}

type TaskResult struct {
	ID       string  `json:"id"`
	Command  string  `json:"command"`
	Stdout   string  `json:"stdout"`
	Stderr   string  `json:"stderr"`
	ExitCode int     `json:"exit_code"`
	Duration float64 `json:"duration_ms"`
	Success  bool    `json:"success"`
	Error    string  `json:"error,omitempty"`
}

type RunnerResult struct {
	Results       []TaskResult `json:"results"`
	TotalTasks    int          `json:"total_tasks"`
	SuccessCount  int          `json:"success_count"`
	FailCount     int          `json:"fail_count"`
	TotalDuration float64      `json:"total_duration_ms"`
}

func main() {
	tasksFile := flag.String("tasks", "", "JSON file containing tasks")
	tasksJSON := flag.String("json", "", "JSON string containing tasks")
	command := flag.String("cmd", "", "Command template with {file} placeholder")
	files := flag.String("files", "", "Comma-separated list of files")
	workDir := flag.String("dir", ".", "Working directory")
	maxWorkers := flag.Int("workers", 0, "Max parallel workers (0 = auto)")
	timeout := flag.Int("timeout", 60, "Timeout per task in seconds")
	flag.Parse()

	var tasks []Task

	if *tasksFile != "" {
		tasks = loadTasksFromFile(*tasksFile)
	} else if *tasksJSON != "" {
		tasks = loadTasksFromJSON(*tasksJSON)
	} else if *command != "" && *files != "" {
		tasks = generateTasks(*command, *files, *workDir)
	} else {
		tasks = loadTasksFromStdin(*workDir)
	}

	if len(tasks) == 0 {
		fmt.Fprintln(os.Stderr, "Error: No tasks to run")
		os.Exit(1)
	}

	result := runTasks(tasks, *maxWorkers, *timeout, *workDir)

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.Encode(result)
}

func loadTasksFromFile(path string) []Task {
	file, err := os.Open(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error opening tasks file: %v\n", err)
		return nil
	}
	defer file.Close()

	var tasks []Task
	json.NewDecoder(file).Decode(&tasks)
	return tasks
}

func loadTasksFromJSON(jsonStr string) []Task {
	var tasks []Task
	json.Unmarshal([]byte(jsonStr), &tasks)
	return tasks
}

func loadTasksFromStdin(workDir string) []Task {
	var tasks []Task
	scanner := bufio.NewScanner(os.Stdin)
	id := 1
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && !strings.HasPrefix(line, "#") {
			tasks = append(tasks, Task{
				ID:      fmt.Sprintf("task_%d", id),
				Command: line,
				Dir:     workDir,
			})
			id++
		}
	}
	return tasks
}

func generateTasks(commandTemplate, filesStr, workDir string) []Task {
	var tasks []Task
	files := strings.Split(filesStr, ",")

	for i, file := range files {
		file = strings.TrimSpace(file)
		if file == "" {
			continue
		}

		cmd := strings.ReplaceAll(commandTemplate, "{file}", file)
		cmd = strings.ReplaceAll(cmd, "{}", file)

		tasks = append(tasks, Task{
			ID:      fmt.Sprintf("task_%d", i+1),
			Command: cmd,
			Dir:     workDir,
		})
	}
	return tasks
}

func runTasks(tasks []Task, maxWorkers, timeout int, defaultDir string) RunnerResult {
	if maxWorkers <= 0 {
		maxWorkers = 4
	}

	start := time.Now()
	result := RunnerResult{
		Results:    make([]TaskResult, len(tasks)),
		TotalTasks: len(tasks),
	}

	jobs := make(chan int, len(tasks))
	var wg sync.WaitGroup
	var mu sync.Mutex

	for w := 0; w < maxWorkers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for idx := range jobs {
				task := tasks[idx]
				taskResult := runTask(task, timeout, defaultDir)

				mu.Lock()
				result.Results[idx] = taskResult
				if taskResult.Success {
					result.SuccessCount++
				} else {
					result.FailCount++
				}
				mu.Unlock()
			}
		}()
	}

	for i := range tasks {
		jobs <- i
	}
	close(jobs)

	wg.Wait()

	result.TotalDuration = float64(time.Since(start).Milliseconds())
	return result
}

func runTask(task Task, timeout int, defaultDir string) TaskResult {
	start := time.Now()
	result := TaskResult{
		ID:      task.ID,
		Command: task.Command,
	}

	workDir := task.Dir
	if workDir == "" {
		workDir = defaultDir
	}

	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, "sh", "-c", task.Command)
	cmd.Dir = workDir

	stdout, err := cmd.Output()
	result.Duration = float64(time.Since(start).Milliseconds())

	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			result.ExitCode = exitErr.ExitCode()
			result.Stderr = string(exitErr.Stderr)
		} else if ctx.Err() == context.DeadlineExceeded {
			result.Error = "timeout exceeded"
			result.ExitCode = -1
		} else {
			result.Error = err.Error()
			result.ExitCode = -1
		}
		result.Success = false
	} else {
		result.ExitCode = 0
		result.Success = true
	}

	result.Stdout = string(stdout)
	return result
}
