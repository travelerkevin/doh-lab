# Phase 3 Demo Script

A conversational walkthrough to read while recording. Target length: **7-8 minutes**.

---

## Before Recording (prep, not on camera)

```bash
cd ~/DOH
git checkout Zhexi-Lu-phase3
docker compose up -d --build

# Generate fresh baseline pcap (5 min)
docker exec client bash -c "bash /opt/phase3-results/scripts/generate-normal-doh.sh"

# Pre-run feature extraction, visualization, ML (about 30 sec)
docker exec monitor bash -c "
python3 /opt/phase3-results/scripts/extract-features.py \
    --normal /opt/phase3-results/normal_doh.pcap \
    --tunnel /opt/phase2-results/doh_bypass.pcap \
    --output /opt/phase3-results/features.csv && \
python3 /opt/phase3-results/scripts/visualize.py \
    --csv /opt/phase3-results/features.csv \
    --output-dir /opt/phase3-results/plots && \
python3 /opt/phase3-results/scripts/train-classifier.py \
    --csv /opt/phase3-results/features.csv \
    --output-dir /opt/phase3-results/ml"
```

Window layout: VS Code on the left, terminal on the right. Open Finder to `phase3/plots/` and `phase3/ml/` for quick access.

Start recording: `Cmd + Shift + 5` → "Record Entire Screen".

---

## Part 1 — Intro (30 s)

Scroll briefly through `phase3/README.md`.

> "Hi, I'm doing Phase 3 of this project. So Phase 1 showed us that DNS tunneling over regular DNS is easy to catch. Phase 2 showed that if you wrap it in DoH, nobody can see it anymore. My job is to figure out: how do we stop this without decrypting the traffic? I came up with three approaches — first, just block known DoH servers. Second, look at traffic patterns. Third, use machine learning."

---

## Part 2 — Phase 3a: Firewall Blocking (1.5 min)

Open `phase3/scripts/block-doh.sh` in VS Code.

> "Phase 3a is the easy one. I just block all the well-known DoH server IPs with a firewall. I put 15 of them in this list — Cloudflare, Google, Quad9, and so on. The script blocks HTTPS to those IPs and also blocks any DNS that doesn't go through our own DNS server."

In terminal:

```bash
docker exec -it client bash
bash /opt/phase3-results/scripts/block-doh.sh apply
```

> "Okay, rules are applied. You can see 18 rules in the firewall now."

```bash
bash /opt/phase3-results/scripts/block-doh.sh test
```

> "I wrote five tests to check it works. Our company DNS still works, but Cloudflare DoH is blocked, Google DoH is blocked, cloudflared proxy is blocked, and direct DNS to 8.8.8.8 is blocked. Five out of five pass.
>
> But there's a problem. Anyone can set up their own DoH server on any IP. You can't put every IP in a blocklist. So blocking alone isn't enough — that's why I also did 3b and 3c."

```bash
bash /opt/phase3-results/scripts/block-doh.sh remove
exit
```

---

## Part 3 — Phase 3b: Traffic Pattern Analysis (2 min)

> "Okay, so DoH is encrypted. We can't see what people are asking. But we can still see how much data they're sending, when they're sending it, and which direction it's going. These patterns are really different between a real person browsing websites and someone tunneling data through DNS."

Open `phase3/scripts/generate-normal-doh.sh` briefly.

> "First, I needed some normal DoH traffic to compare with. This script pretends to be a regular user — it runs cloudflared and visits about 50 websites, with random wait times like a real person reading pages. I let it run for 5 minutes and got about 110 KB of normal DoH traffic."

Show `phase3/normal_doh.pcap` in Finder.

Open `phase3/scripts/extract-features.py` briefly.

> "Then I pull 25 features out of both my normal traffic and the attack traffic from Phase 2. I chop the traffic into 10-second windows and measure things like packet count, packet size, how often packets come in, which direction they go, and so on."

In terminal:

```bash
docker exec -it monitor bash
python3 /opt/phase3-results/scripts/extract-features.py \
    --normal /opt/phase3-results/normal_doh.pcap \
    --tunnel /opt/phase2-results/doh_bypass.pcap \
    --output /opt/phase3-results/features.csv
```

> "Okay, 105 windows total — each one labeled as either normal or tunnel."

Open `phase3/plots/feature_distributions.png` full screen (press `F` in Preview).

> "Here's every feature side by side. Blue is normal browsing, red is the tunnel. You can see for most features, the two colors barely overlap."

Open `phase3/plots/top_separating_features.png`.

> "These are the six features that separate the two classes the best. Mostly it's packet size stuff, and the upload-to-download ratio."

Open `phase3/plots/feature_summary.txt`.

> "Just to give you a number — normal traffic has an upload-download ratio around 1.2. The tunnel is around 3.2. That's a huge gap, and no sample falls in the middle."

---

## Part 4 — Phase 3c: Machine Learning (2 min)

> "Now for the last part — training a classifier. I picked three models. Logistic Regression is simple and linear — if even this works, it means the features are really good. Random Forest and XGBoost are more powerful tree-based models. I use 5-fold cross-validation because my dataset is small."

In terminal:

```bash
python3 /opt/phase3-results/scripts/train-classifier.py \
    --csv /opt/phase3-results/features.csv \
    --output-dir /opt/phase3-results/ml
```

Wait for it to finish (~15 sec).

> "Okay, all three models score above 97%. Logistic Regression actually hits 100%, which means one straight line in the feature space is enough to split the two classes."

Open `phase3/ml/confusion_matrices.png`.

> "Confusion matrices — basically no mistakes."

Open `phase3/ml/roc_curves.png`.

> "ROC curves — AUC is almost 1 for all three."

Open `phase3/ml/feature_importance.png`.

> "And these are the features the models use the most. Packet size and timing, just like we saw in 3b."

---

## Part 5 — Being Honest About Limitations (45 s)

> "I should be honest here — 100% accuracy sounds great, but it's a bit misleading. My normal traffic and the attack traffic were recorded on different machines at different times. So the models might be partly learning 'which computer is this' instead of 'is this an attack.' In a real setup, you'd want to record both on the same machine.
>
> Also, real attackers can make their tunnels much sneakier — add fake delays, pad packets to random sizes, mimic normal browsing speed. The tool I used, dnscat2, is pretty noisy and easy to catch. But even so, the main point holds: even when traffic is encrypted, the behavior gives it away."

---

## Part 6 — Wrap Up (30 s)

> "So that's Phase 3. The firewall handles most casual users. The machine learning catches the smart ones who set up their own DoH servers. And none of this needs to decrypt any traffic. Everything is on my branch, Zhexi-Lu-phase3. Thanks!"

---

## Recording Tips

- Terminal font size: `Cmd +` to 16-18 pt
- Pause 2 seconds after each command output so viewers can read
- Open PNGs full-screen in Preview (press `F`)
- Speak slowly and clearly
- After recording, trim intro/outro in QuickTime Player
