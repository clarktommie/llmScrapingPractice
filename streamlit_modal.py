import shlex
import subprocess
from pathlib import Path
import os
from dotenv import load_dotenv

import modal
#
#
# RUN WITH MODAL DEPLOY < python streamlit_modal.py >
#
#

# Load environment variables from .env file
load_dotenv()

# Point to your Streamlit app
streamlit_script_local_path = Path(__file__).parent / "streamlit_app.py"
streamlit_script_remote_path = "/root/streamlit_app.py"

# Build the Modal image
image = (
    modal.Image.debian_slim(python_version="3.12")  # match your local env
    .uv_pip_install(
        "streamlit", "supabase", "pandas", "plotly", "python-dotenv",
        "pydeck", "folium", "streamlit-folium"
    )
    .env({"FORCE_REBUILD": "true"})  # force rebuild when needed
    .add_local_file(streamlit_script_local_path, streamlit_script_remote_path)
)


app = modal.App(name="book-browser", image=image)

if not streamlit_script_local_path.exists():
    raise RuntimeError(
        "Streamlit app not found at expected path"
        )

@app.function(
    secrets=[modal.Secret.from_name("philly_secrets")],
    allow_concurrent_inputs=100
)
@modal.web_server(8000)
def run():
    target = shlex.quote(streamlit_script_remote_path)
    cmd = f"streamlit run {target} --server.port 8000 --server.enableCORS=false --server.enableXsrfProtection=false"

    # Build environment variables
    env_vars = {}
    if os.getenv("SUPABASE_KEY"):
        env_vars["SUPABASE_KEY"] = os.getenv("SUPABASE_KEY")
    if os.getenv("SUPABASE_URL"):
        env_vars["SUPABASE_URL"] = os.getenv("SUPABASE_URL")

    # Include full environment so PATH etc. are preserved
    env_vars.update(os.environ)

    subprocess.Popen(cmd, shell=True, env=env_vars)
