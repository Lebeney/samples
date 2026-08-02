"""
Monte Carlo of the ACTUAL Step Index trade from the MT5 journal (acct 101638786).

Replays the exact 9-stack over many random Step Index paths and asks:
  what fraction TRIPLE the account (reach the profit you banked) vs
  what fraction get MARGIN-CALLED first?

Everything is pinned to the real log so this isn't a guess:
  * 9 short entries of 0.1 lot, no stops (prices from the journal).
  * Take-profit barrier = your real exit (7815.4) -> the +$24.6 that made $8 -> ~$32.6.
  * Step Index = symmetric random walk, fixed 0.1 step, p(up)=p(down)=0.5
    (confirmed by the 0.1-grid fills in the log).
  * $/point pinned so the sim reproduces $8 -> $32.6 (=> ~$9 per 1.0 point on the
    full 0.9-lot stack), which also fixes how close the margin-call was.
"""
import numpy as np

ENTRIES = np.array([7818.6, 7818.4, 7818.4, 7818.2, 7818.0,
                    7817.8, 7817.9, 7817.9, 7818.0])       # 9 short fills, 0.1 lot each
N_LOTS = len(ENTRIES)                                       # 9 x 0.1 lot
SUM_ENTRY = ENTRIES.sum()                                   # 70363.2
ENTRY_AVG = SUM_ENTRY / N_LOTS                              # 7818.133
STEP = 0.1
START_EQ = 8.0
EXIT_PRICE = 7815.4                                         # your actual bulk-close
STOPOUT_FRAC = 0.50                                         # Deriv MT5 stop-out = 50% margin
MARGIN_PER_LOT = 0.85                                       # implied: 9 fit in $8, 10th = "No money"


def equity(price):
    """Account equity as a function of current Step price (short 0.9 lots)."""
    # $/point pinned to reproduce $8 -> $32.6 at the real exit:
    #   gain = (SUM_ENTRY - N_LOTS*EXIT_PRICE) * pt_val  and we want gain = 24.6
    pnl_points = SUM_ENTRY - N_LOTS * price
    pt_val = 24.6 / (SUM_ENTRY - N_LOTS * EXIT_PRICE)       # ~= 1.0  ($ per point per 0.1 lot)
    return START_EQ + pnl_points * pt_val


def barrier_ticks():
    profit_ticks = round((ENTRY_AVG - EXIT_PRICE) / STEP)          # price must FALL this many ticks
    margin_used = N_LOTS * MARGIN_PER_LOT
    # two ruin definitions (up-moves), bracketing reality:
    ruin_prices = {
        "Deriv 50% stop-out": _price_for_equity(STOPOUT_FRAC * margin_used),
        "full wipe (equity 0)": _price_for_equity(0.0),
    }
    ruin = {k: round((v - ENTRY_AVG) / STEP) for k, v in ruin_prices.items()}
    return profit_ticks, ruin


def _price_for_equity(eq_target):
    pt_val = 24.6 / (SUM_ENTRY - N_LOTS * EXIT_PRICE)
    # eq_target = START_EQ + (SUM_ENTRY - N_LOTS*price)*pt_val  -> solve price
    return (SUM_ENTRY - (eq_target - START_EQ) / pt_val) / N_LOTS


def simulate(profit_ticks, ruin_ticks, n_paths=200_000, max_steps=200_000, seed=0):
    """Symmetric +-1 tick walk with two absorbing barriers. Returns outcome array
    (+1 = hit profit/triple, -1 = hit ruin)."""
    rng = np.random.default_rng(seed)
    pos = np.zeros(n_paths, dtype=np.int32)
    done = np.zeros(n_paths, dtype=bool)
    outcome = np.zeros(n_paths, dtype=np.int8)
    for _ in range(max_steps):
        mv = rng.integers(0, 2, n_paths).astype(np.int32) * 2 - 1
        pos[~done] += mv[~done]
        hit_profit = (~done) & (pos <= -profit_ticks)      # price fell enough -> short wins
        hit_ruin = (~done) & (pos >= ruin_ticks)           # price rose enough -> margin call
        outcome[hit_profit] = 1
        outcome[hit_ruin] = -1
        done |= hit_profit | hit_ruin
        if done.all():
            break
    return outcome


def main():
    import matplotlib
    matplotlib.use("Agg"); import matplotlib.pyplot as plt

    profit_ticks, ruin = barrier_ticks()
    print(f"Entry avg {ENTRY_AVG:.3f} | profit target {EXIT_PRICE} = {profit_ticks} ticks DOWN")
    print(f"Reproduced P&L at target: +${equity(EXIT_PRICE)-START_EQ:.1f}  "
          f"(${START_EQ:.0f} -> ${equity(EXIT_PRICE):.1f})\n")

    results = {}
    for label, rticks in ruin.items():
        oc = simulate(profit_ticks, rticks)
        p_triple = float(np.mean(oc == 1)); p_ruin = float(np.mean(oc == -1))
        win_amt = equity(EXIT_PRICE) - START_EQ
        loss_amt = START_EQ - max(0.0, equity(ENTRY_AVG + rticks * STEP))
        ev = p_triple * win_amt - p_ruin * loss_amt
        results[label] = (p_triple, p_ruin, win_amt, loss_amt, ev, rticks)
        print(f"--- ruin = {label} ({rticks} ticks UP, ~{rticks*STEP:.1f} pts) ---")
        print(f"  P(triple to ~$32)   = {p_triple*100:5.1f}%")
        print(f"  P(margin-called)    = {p_ruin*100:5.1f}%")
        print(f"  win +${win_amt:.1f} / lose -${loss_amt:.1f}  ->  EV per attempt = ${ev:+.2f}")
        print(f"  survive 5 repeats   = {(1-p_ruin)**5*100:.2f}%\n")

    # ---- plot: outcome split + survival vs number of repeats -------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    labels = list(results.keys())
    triples = [results[k][0] * 100 for k in labels]
    ruins = [results[k][1] * 100 for k in labels]
    x = np.arange(len(labels))
    ax1.bar(x, triples, 0.5, label="triple to ~$32", color="#2f9e44")
    ax1.bar(x, ruins, 0.5, bottom=triples, label="margin-called (lose the $8)", color="#c92a2a")
    for i, (t, r) in enumerate(zip(triples, ruins)):
        ax1.text(i, t/2, f"{t:.0f}%", ha="center", va="center", color="white", fontsize=10)
        ax1.text(i, t + r/2, f"{r:.0f}%", ha="center", va="center", color="white", fontsize=10)
    ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_ylabel("% of attempts"); ax1.set_title("One attempt: your exact 9-stack on random Step paths")
    ax1.legend(fontsize=8)

    reps = np.arange(1, 11)
    for k in labels:
        p_ruin = results[k][1]
        ax2.plot(reps, (1 - p_ruin) ** reps * 100, marker="o", label=k)
    ax2.set_xlabel("number of times you repeat this"); ax2.set_ylabel("% chance still alive")
    ax2.set_title("Probability of surviving repeated attempts"); ax2.set_yscale("log")
    ax2.grid(alpha=0.3); ax2.legend(fontsize=8)
    fig.suptitle("Step Index 9-stack (from journal): tripling was the ~1-in-6 lucky side of a "
                 "zero-EV gamble", fontsize=11)
    fig.tight_layout()
    fig.savefig("step_montecarlo.png", dpi=110)
    print("saved step_montecarlo.png")


if __name__ == "__main__":
    main()
