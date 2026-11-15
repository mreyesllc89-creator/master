"""Write an MT5 .set from the shipped 152-input preset with the calibrated inputs replaced."""
import io

TF = {60: 16385, 120: 16386, 180: 16387, 240: 16388, 360: 16390, 480: 16392, 720: 16396, 1440: 16408,
      10080: 32769}


def write(template, path, p, header):
    lines = [l.rstrip("\r\n") for l in io.open(template, encoding="utf-16")]
    fmt = {}
    for k, v in p.items():
        if k in ("MainTimeframe", "MicroTimeframe", "VolATRTimeframe"):
            fmt[k] = str(TF.get(int(v), int(v)))
        elif k in ("UpdateTrendInsideBasket", "TrailingEnabled", "VolLotEnabled", "VolDistEnabled", "CushionEnabled",
                   "CycleLossPctEnabled", "NewZonesEnabled"):
            fmt[k] = "true" if v else "false"
        elif k in ("MainFastEMA", "MainSlowEMA", "MicroFastEMA", "MicroSlowEMA", "TrendSource", "VolATRPeriod",
                   "StopCooldownMinutes", "MaxBasketAgeMinutes"):
            fmt[k] = str(int(v))
        else:
            fmt[k] = ("%.4f" % v).rstrip("0").rstrip(".") if v != int(v) else "%.1f" % v
    out = ["; " + h for h in header]
    for l in lines:
        if l.startswith(";") or "=" not in l:
            continue
        k = l.split("=", 1)[0]
        out.append(f"{k}={fmt[k]}" if k in fmt else l)
    io.open(path, "w", encoding="utf-16", newline="\r\n").write("\n".join(out) + "\n")
