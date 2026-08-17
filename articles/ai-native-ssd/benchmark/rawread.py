"""Pure read-bandwidth test on corpus.bin, no compute. Reads the first 8 GB
(cold: page cache holds only the file tail after the full scan)."""
import time

PATH = r"D:\aissd-bench\corpus.bin"
TOTAL = 8 * 1024**3
CHUNK = 64 * 1024**2

for label, buf in [("unbuffered", 0), ("buffered-8MB", 8 * 1024**2)]:
    t0 = time.time()
    got = 0
    with open(PATH, "rb", buffering=buf) as f:
        while got < TOTAL:
            b = f.read(CHUNK)
            if not b:
                break
            got += len(b)
    el = time.time() - t0
    print(f"{label}: {got/1e9:.1f} GB in {el:.1f}s = {got/1e9/el:.2f} GB/s", flush=True)
