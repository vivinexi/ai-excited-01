# Make the AI judge excited

Entry for the make.fun bounty `ai-excited-01`.

The program writes one image to `/output/entry.png`: a gigantic ocean wave
curling into the shape of a galloping horse — foam mane and tail, a tiny
surfer at its base for scale — backlit by a blazing orange sunset. The wave
doesn't just carry a horse, it *is* the horse.

## How it works

`main.py` copies the image this repository holds (`art.jpg`) to
`/output/entry.png`. No network access, no randomness: every run writes
exactly the same bytes.

## Run it

```bash
python3 main.py
```
