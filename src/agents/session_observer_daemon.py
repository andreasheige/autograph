import time
import sys
import threading

from src.agents.session_observer import SessionObserverAgent
from src.agents.session_trigger import MultiRepositorySessionTriggerAgent
from config.settings import Config

def run_daemon(interval_seconds: int = 60):
    """
    Runs the SessionObserverAgent and SessionTriggerAgent together.
    """
    print(f"🚀 [SessionObserver-Daemon] Starting continuous observation + trigger mode.")
    
    agent = SessionObserverAgent()
    
    trigger_agent = MultiRepositorySessionTriggerAgent(
        search_dir=Config.SEARCH_DIR,
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
    except Exception as error:
        print(f"\n❌ [SessionObserver-Daemon] CRITICAL ERROR: {error}")
        sys.exit(1)

if __name__ == "__main__":
    run_daemon(60)
