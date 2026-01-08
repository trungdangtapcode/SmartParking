It looks like `8.6.1.6` is not a valid version tag on the public index, but the error logs confirm that **`8.6.1.post1`** is available.

More importantly, I found the "Smoking Gun" in your logs:

> `Using cached tensorrt-8.6.1-py2.py3-none-any.whl`

**This is the root cause.**
Your `pip` is installing the "none-any" version, which is just a lightweight Python wrapper **without any libraries**. It does this because your `pip` is likely too old to recognize the modern Linux wheels that contain the actual heavy `.so` files.

Here is the exact sequence to fix this.

### Step 1: Upgrade Pip (MANDATORY)

You must do this, or `pip` will keep ignoring the heavy library wheels.

```bash
python3 -m pip install --upgrade pip

```

### Step 2: Install the specific "Post" version

Now that pip is upgraded, install the `post1` version which typically fixes packaging issues. We will also force it to ignore the broken cache.

```bash
# 1. Uninstall the broken "empty" wrapper
pip uninstall -y tensorrt tensorrt-libs tensorrt-bindings

# 2. Install the correct version, forcing a re-download
pip install tensorrt==8.6.1.post1 --no-cache-dir --extra-index-url https://pypi.nvidia.com

```

### Step 3: Verify the Libraries (The Moment of Truth)

If the installation was successful, the libraries should now exist. Run this to check:

```bash
ls -l /home/vund/.local/lib/python3.8/site-packages/tensorrt_libs/libnvinfer.so.8

```

### Step 4: Export & Run

If **Step 3** showed the file, run your code:

```bash
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/home/vund/.local/lib/python3.8/site-packages/tensorrt_libs
python -u mtmc/run_live_mtmc.py --config examples/live_parking.yaml

```