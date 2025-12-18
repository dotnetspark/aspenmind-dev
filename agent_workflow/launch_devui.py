"""
Launch DevUI for the exam generation workflow.
"""
import sys
import os
import logging
from datetime import datetime

# Configure logging to both file and console
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

log_filename = os.path.join(log_dir, f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()  # Also print to console
    ]
)

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent_framework.devui import serve
from workflows.exam_generation_workflow import create_exam_generation_workflow

if __name__ == "__main__":
    # Create the workflow
    logger.info("Creating exam generation workflow...")
    workflow = create_exam_generation_workflow()
    
    # Launch DevUI with the workflow
    logger.info(f"Starting DevUI - Logs will be saved to: {log_filename}")
    print("Starting DevUI for Exam Generation Workflow...")
    print(f"Logs: {log_filename}")
    print("This will open in your browser automatically.")
    print("\nTo test, send a message like:")
    print('  "Generate 3 items for topic TP.2"')
    print()
    
    serve(
        entities=[workflow],
        auto_open=True  # Opens browser automatically
    )
