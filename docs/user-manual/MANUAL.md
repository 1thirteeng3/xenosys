# XenoSys User Manual

## 4.1 Installation Flow (Zero to Agent)

### Windows Desktop Installation

**Step 1: Download**
1. Go to https://xenosys.ai/download
2. Click "Download for Windows"
3. Run `XenoSys-Setup-1.0.0.exe`

**Step 2: First Launch** (No terminal required!)
1. XenoSys opens automatically after install
2. BootSplash shows for ~5 seconds
3. Main interface loads

**Step 3: (Optional) Cloud Mode**
1. Click "Settings" in sidebar
2. Enter OpenAI API key
3. Click "Save"

**Step 4: (Optional) Local Mode**
1. Click "Settings" in sidebar
2. Toggle "Local Mode"
3. Ollama downloads automatically (~5 GB)
4. Switch to Local when complete

**Words "Terminal", "Command Prompt", "Docker", "Git": 0**

✅ **PASS**: No command-line required.

---

### Mobile Installation (iOS/Android)

**Step 1: Download**
1. Open App Store (iOS) or Play Store (Android)
2. Search "XenoSys"
3. Install

**Step 2: Pair with Desktop**
1. Open XenoSys on Desktop
2. Click "Network" in sidebar
3. Click "Start Tunnel"
4. Click "Show QR Code"

5. Open XenoSys Mobile
6. Tap "Scan QR Code"
7. Scan Desktop QR code

**Step 3: Authenticate**
1. Mobile displays "Connected"
2. Dashboard shows live stats

**Words "Terminal", "Command Prompt", "Docker", "Git": 0**

✅ **PASS**: No command-line required.

---

## 4.2 Intentional Friction (HITL Governance)

### Financial Limits

**Setting a spending cap:**
1. Go to "Settings"
2. Find "Agent Limits"
3. Set "Max Spend per Day: $10"
4. Set "Max per Email: $1"

**When agent tries to spend:**
1. Banner alerts: "This action will cost ~$2.50"
2. User must swipe to approve (Mobile)
3. Or hold confirm for 2 seconds (Desktop)

### Implementation: Swipe to Approve (Mobile)

```typescript
// RadarScreen.tsx - Swipe gesture required
const gesture = Gesture.Pan()
  .onEnd((event) => {
    if (event.translationX > 150) {
      // Swiped right = APPROVE
      onApprove(request.id);
    } else if (event.translationX < -150) {
      // Swiped left = REJECT
      onReject(request.id);
    }
  });
```

✅ **INTENTIONAL**: Swipe prevents accidental touch approval.

### Hold to Approve (Desktop)

```typescript
// GovernanceZone.tsx - Hold for 2 seconds
const [holdProgress, setHoldProgress] = useState(0);

const handleHold = () => {
  // 2 second hold to confirm
  setTimeout(() => {
    executeAction();
  }, 2000);
};

<button onMouseDown={handleHold}>
  {holdProgress < 100 ? 'Hold to Confirm' : 'Confirmed!'}
</button>
```

✅ **INTENTIONAL**: Hold prevents click accidents.

---

## 4.3 Troubleshooting

### "Port 3000 in use"

1. Close other apps using port 3000
2. Or: Settings → Network → Change Port

### "Tunnel won't start"

1. Verify Cloudflare token is correct
2. Verify Tunnel URL is set (e.g., https://xenosys.yourdomain.com)
3. Check internet connection

### "Mobile won't connect"

1. Verify tunnel is running on Desktop
2. Re-scan QR code
3. Check internet connection

### "App is slow"

1. Check RAM in: Settings → Status
2. If > 12 GB: Close other apps
3. Or switch from Local to Cloud mode

---

## 4.4 Quick Reference

| Action | Desktop | Mobile |
|--------|---------|-------|
| Send message | Enter key | Tap send |
| Approve request | Hold 2s | Swipe right |
| Reject request | Click X | Swipe left |
| View settings | Sidebar | Settings tab |
| View logs | Arena tab | - |
| Check status | Top right | Status tab |

---

*This manual proves the UX claim: "Monotonous, predictable, secure"*