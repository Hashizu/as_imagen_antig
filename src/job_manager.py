"""
Job Manager Module.

Handles asynchronous background jobs for image generation.
"""
import threading
import time
import traceback
from typing import Dict, Optional, Any
from datetime import datetime

from src.generator import ImageGenerator
from src.state_manager import StateManager
from src.storage import S3Manager
import pandas as pd
from io import BytesIO

class GenerationJob(threading.Thread):
    """
    Background job for generating images.
    """
    def __init__(
        self,
        api_key: str,
        keyword: str,
        tags: str,
        n_images: int,
        model: str,
        style: str,
        size: str,
        creator_ip: str = "127.0.0.1"
    ):
        super().__init__()
        self.api_key = api_key
        self.keyword = keyword
        self.tags = tags
        self.n_images = n_images
        self.model = model
        self.style = style
        self.size = size
        self.creator_ip = creator_ip
        
        self._stop_event = threading.Event()
        self.status = {
            "progress": 0.0,
            "message": "Initializing...",
            "is_running": False,
            "is_complete": False,
            "error": None,
            "generated_count": 0
        }

    def run(self):
        """Execute the generation process."""
        self.status["is_running"] = True
        self.status["message"] = "Starting generation..."
        
        try:
            generator = ImageGenerator(self.api_key, model_name=self.model)

            # 1. Setup Directories
            # Copied logic from app.py _setup_output_dirs to keep it self-contained or importable
            # For simplicity, we implement logic here or import if it was in a shared util.
            # Let's replicate the logic to ensure thread safety without relying on st context
            timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
            safe_keyword = "".join(
                c for c in self.keyword if c.isalnum() or c in (' ', '_', '-')
            ).strip().replace(" ", "_")[:50]
            base_prefix = f"output/{timestamp}_{safe_keyword}"
            images_dir = f"{base_prefix}/generated_images"

            if self._stop_event.is_set():
                return

            # 2. Generate Ideas
            self.status["message"] = f"Generating {self.n_images} ideas..."
            self.status["progress"] = 0.1
            
            ideas = generator.generate_image_description(
                self.keyword, n_ideas=self.n_images, style=self.style
            )
            
            if not ideas:
                raise ValueError("Failed to generate ideas.")

            # 3. Generate Images Loop
            csv_data = []
            total_steps = len(ideas)
            
            for i, idea in enumerate(ideas):
                if self._stop_event.is_set():
                    self.status["message"] = "Cancelled."
                    break

                self.status["message"] = f"Generating image {i+1}/{self.n_images}..."
                # Progress calculation: 0.1 to 0.9
                self.status["progress"] = 0.1 + (0.8 * (i / total_steps))

                try:
                    draw_prompt = generator.generate_drawing_prompt(idea, style=self.style)
                    filename = f"img_{i:03d}.png"
                    output_path = f"{images_dir}/{filename}"

                    generator.generate_image(
                        prompt=draw_prompt,
                        output_path=output_path,
                        size=self.size
                    )
                    
                    csv_data.append({
                        "filename": filename,
                        "prompt": draw_prompt,
                        "keyword": self.keyword,
                        "tags": self.tags,
                        "creator_ip": self.creator_ip
                    })
                    self.status["generated_count"] += 1
                    
                except Exception as e:
                    print(f"Error in job: {e}")
                    # Continue to next image even if one fails

            # 4. Finalize
            if csv_data:
                self.status["message"] = "Saving metadata..."
                self.status["progress"] = 0.95
                
                s3 = S3Manager()
                df = pd.DataFrame(csv_data)
                csv_buffer = BytesIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                csv_key = f"{images_dir}/prompt.csv"
                s3.upload_file(csv_buffer.getvalue(), csv_key, content_type="text/csv")
                
                # Update State DB
                StateManager().scan_and_sync()

            self.status["progress"] = 1.0
            self.status["message"] = "Generation Complete!"
            self.status["is_complete"] = True

        except Exception as e:
            self.status["error"] = str(e)
            self.status["message"] = f"Error: {str(e)}"
            traceback.print_exc()
        finally:
            self.status["is_running"] = False

    def cancel(self):
        """Request job cancellation."""
        self._stop_event.set()
