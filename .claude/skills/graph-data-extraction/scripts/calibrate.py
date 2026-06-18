#!/usr/bin/env python3
"""
calibrate.py - detect the plot frame and tick-label pixel centers to help
build a pixel->data mapping. Run this, read the printed candidates, then map
each tick center to its printed value (which you read off the image yourself).

Usage:
    python3 calibrate.py IMAGE.png
    python3 calibrate.py IMAGE.png --dark 130   # for light-gray frames

This does NOT guess tick values (it can't read axis numbers reliably); it
gives you pixel positions to pair with the values you see in the figure.
"""
import argparse, numpy as np, cv2


def group(idx, gap):
    if len(idx) == 0:
        return []
    g, c = [], [idx[0]]
    for x in idx[1:]:
        if x - c[-1] <= gap:
            c.append(x)
        else:
            g.append(int(np.mean(c))); c = [x]
    g.append(int(np.mean(c)))
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--dark", type=int, default=80,
                    help="darkness threshold for frame lines (raise for light frames)")
    args = ap.parse_args()

    im = cv2.imread(args.image)
    if im is None:
        raise SystemExit(f"could not read {args.image}")
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    H, W = gray.shape
    print(f"image size: W={W} H={H}")

    dark = gray < args.dark
    vcols = np.where(dark.sum(axis=0) > 0.4 * H)[0]
    hrows = np.where(dark.sum(axis=1) > 0.3 * W)[0]
    vframe = group(vcols, 10)
    hframe = group(hrows, 10)
    print(f"vertical frame x candidates:   {vframe}")
    print(f"horizontal frame y candidates: {hframe}")

    if len(vframe) >= 2 and len(hframe) >= 2:
        left, right = vframe[0], vframe[-1]
        top, bot = hframe[0], hframe[-1]
        print(f"\nassuming frame: left={left} right={right} top={top} bot={bot}")

        xband = (gray[bot + 6: bot + 42, :] < 100)
        xcent = group(np.where(xband.sum(axis=0) > 1)[0], 25)
        print(f"\nx tick label centers (px): {xcent}")
        print("  -> pair these left-to-right with the x values printed on the axis")

        yband = (gray[:, max(0, left - 95): max(1, left - 6)] < 100)
        ycent = group(np.where(yband.sum(axis=1) > 2)[0], 20)
        print(f"y tick label centers (px): {ycent}")
        print("  -> pair these top-to-bottom with the y values printed on the axis")
        print("\nThen: ax = np.polyfit(pixels, values, 1); value = ax[0]*pixel + ax[1]")
        print("If frame/ticks look wrong, view a margin crop and read edges by eye,")
        print("or re-run with a different --dark threshold.")
    else:
        print("\nframe not cleanly detected; try --dark with a higher value (e.g. 130),")
        print("or view a margin crop and read the edge/tick pixels manually.")


if __name__ == "__main__":
    main()
