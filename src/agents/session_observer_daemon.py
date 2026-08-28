import time
import sys
from src.agents.session_observer import SessionObserverAgent

def run_daemon(interval_seconds: int = 60):
    """
    Runs the SessionObserverAgent and SessionTriggerAgent together.
    """
    print(f"🚀 [SessionObserver-Daemon] Starting continuous observation + trigger mode.")
    
    agent = SessionObserverAgent()
    
    # The trigger agent needs the commit handler as a callback
    trigger_agent = SessionTriggerAgent(
        repo_path=".", 
        trigger_callback=agent.handle_commit_event
    )
    
    # We run the observer pulse loop in a
    def observer_loop():
        print(f"⏱️  Pulse interval: {interval_seconds} seconds.")
        while True:
            agent.run_once()
            time.sleep(interval_seconds)

    observer_thread = threading.Thread(target=observer_loop, daemon=True)
    observer_thread.start()
    
    try:
        # The trigger agent blocks here, monitoring git
        trigger_agent.start()
            
    except KeyboardInterrupt:
        print("\n🛑 [SessionObserver-Daemon] Shutting down gracefully...")
        trigger_agent.stop()
        agent.stop()
    except Exception as e:
        print(f"\n❌ [SessionObserver-Daemon] CRITICAL ERROR: {template_error} e}")
        sys.exit(1)

if __name__ == "__main__":
    import os
    # Pulse every 60 seconds by default
    run_daemon(60)
