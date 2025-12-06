"""
scheduler.py - Cooperative task scheduler for OpenPonyLogger
"""

import time

class Task:
    """Base class for scheduled tasks"""
    def __init__(self, name, interval_ms):
        self.name = name
        self.interval_ms = interval_ms
        self.last_run_time = 0
        self.run_count = 0
        self.total_time = 0
        self.enabled = True
        
    def is_ready(self, current_time_ms):
        """Check if task should run"""
        if not self.enabled:
            return False
        return (current_time_ms - self.last_run_time) >= self.interval_ms
    
    def execute(self, current_time_ms):
        """Run the task and track timing"""
        start = time.monotonic()
        self.run()
        duration = time.monotonic() - start
        
        self.last_run_time = current_time_ms
        self.run_count += 1
        self.total_time += duration
        
        return duration
    
    def run(self):
        """Override this in subclasses"""
        raise NotImplementedError
    
    def get_stats(self):
        """Get performance statistics"""
        if self.run_count == 0:
            return {
                'name': self.name,
                'runs': 0,
                'avg_ms': 0,
                'total_ms': 0
            }
        
        avg_time = (self.total_time / self.run_count) * 1000
        return {
            'name': self.name,
            'runs': self.run_count,
            'avg_ms': avg_time,
            'total_ms': self.total_time * 1000
        }


class Scheduler:
    """Cooperative task scheduler"""
    def __init__(self):
        self.tasks = []
        self.start_time = time.monotonic()
        self.running = False
        
    def add_task(self, task):
        """Register a task"""
        self.tasks.append(task)
        print(f"[Scheduler] Added task: {task.name} @ {task.interval_ms}ms")
    
    def run(self):
        """Main scheduler loop"""
        self.running = True
        print("\n[Scheduler] Starting main loop...")
        
        try:
            while self.running:
                current_time_ms = int((time.monotonic() - self.start_time) * 1000)
                
                # Check each task
                for task in self.tasks:
                    if task.is_ready(current_time_ms):
                        task.execute(current_time_ms)
                
                # Small sleep to prevent busy-wait
                time.sleep(0.001)  # 1ms
                
        except KeyboardInterrupt:
            print("\n[Scheduler] Stopped by user")
            self.running = False
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
    
    def print_stats(self):
        """Print performance statistics"""
        print("\n" + "=" * 60)
        print("Task Performance Statistics")
        print("=" * 60)
        print(f"{'Task':<20} {'Runs':<10} {'Avg (ms)':<12} {'Total (ms)':<12}")
        print("-" * 60)
        
        for task in self.tasks:
            stats = task.get_stats()
            print(f"{stats['name']:<20} {stats['runs']:<10} {stats['avg_ms']:<12.2f} {stats['total_ms']:<12.1f}")
        
        print("=" * 60)
