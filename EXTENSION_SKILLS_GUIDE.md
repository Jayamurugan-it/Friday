# Friday AI — Extension Skills System

**Add custom browser automation to Friday's Chrome extension!**

---

## What You Asked For

✅ **User asks Friday**: "Friday, extension skill template"  
✅ **Friday opens**: `EXTENSION_SKILL_TEMPLATE.md`  
✅ **User uploads to Claude**: "Write me a YouTube play/pause skill"  
✅ **Claude generates**: Complete JavaScript code  
✅ **User pastes**: Into `extension/skills/youtube_control.js`  
✅ **Reload extension**: Skills load automatically  
✅ **User says**: "Friday, pause youtube" → Works!  

---

## The Complete Workflow

### Step 1: Get Template
```
User: "Friday, extension skill template"
Friday: Opens EXTENSION_SKILL_TEMPLATE.md
```

### Step 2: Upload to Claude
User uploads template to Claude.ai and says:
```
"Write me a skill that controls YouTube:
- Play/pause video
- Set volume
- Skip forward/backward
- Get video info"
```

### Step 3: Claude Generates
Claude returns complete JavaScript code:
```javascript
const YouTubeControl = {
  name: "YouTube Controller",
  commands: {
    play_youtube: { ... },
    pause_youtube: { ... },
    youtube_volume: { ... }
  }
};
window.FridaySkills.register(YouTubeControl);
```

### Step 4: User Pastes
User copies code → pastes into `extension/skills/youtube_control.js`

### Step 5: Reload Extension
- Go to `chrome://extensions`
- Find Friday AI extension
- Click reload button (↻)

### Step 6: Use It!
```
User: "Friday, pause youtube"
Friday: ⏸️ Paused video
```

---

## What's in EXTENSION_SKILL_TEMPLATE.md

The template includes **5 complete working examples**:

### 1. YouTube Controller (150+ lines)
- Play/pause/toggle
- Volume control
- Skip forward/backward
- Get video info
- Theater mode
- Fullscreen
- Playback speed
- Custom keyboard shortcuts

### 2. Netflix Controller
- Play/pause
- Skip intro
- Next episode
- Toggle subtitles

### 3. Gmail Shortcuts
- Compose email
- Search emails
- Mark as read
- Archive
- Get unread count

### 4. Twitter/X Actions
- Open composer
- Like tweets
- Scroll timeline

### 5. Universal Reader
- Extract main content from any site
- Get all links
- Count images
- Works everywhere (no domain restriction)

---

## File Structure

```
extension/
├── skills/                    ← NEW: Drop .js files here
│   ├── README.md             ← Instructions
│   └── (your_skill.js)       ← Your custom skills
├── src/
│   ├── content.js            ← UPGRADED: FridaySkills registry
│   ├── background.js         ← UPGRADED: Skill loading
│   ├── popup.html
│   └── popup.js
└── manifest.json
```

---

## How It Works Internally

### 1. Skills Register Themselves
```javascript
// In your skill file
window.FridaySkills.register({
  name: "MySkill",
  commands: { ... }
});
```

### 2. Friday Detects Available Skills
```javascript
// content.js automatically loads:
window.FridaySkills = {
  _skills: {},
  register: function(skill) { ... },
  list: function() { ... },
  get: function(name) { ... }
};
```

### 3. User Invokes Skill
```
User: "Friday, play youtube"
↓
Friday AI (backend) recognizes "play youtube"
↓
Sends to extension: {command: "play_youtube", args: {}}
↓
content.js finds YouTubeControl skill
↓
Executes handler
↓
Returns result to user
```

---

## Commands Available

```bash
# Show extension skill template
Friday, extension skill template

# Show Python skill template (for backend)
Friday, skill template

# Open extension skills folder
Friday, open extension skills

# List loaded extension skills
Friday, list extension skills
```

---

## Example: YouTube Controller Usage

After installing the YouTube skill from template:

```
Friday, play youtube          → ▶️ Playing video
Friday, pause youtube         → ⏸️ Paused video
Friday, youtube volume 80     → 🔊 Volume set to 80%
Friday, youtube skip 30       → ⏩ Skipped 30s forward
Friday, youtube info          → Shows title, time, status
Friday, youtube speed 1.5     → ⚡ Playback speed: 1.5x
Friday, youtube fullscreen    → ⛶ Toggled fullscreen
```

---

## Skill Capabilities

Extension skills can:

✅ **Access full DOM** — read/modify any element  
✅ **Click buttons** — simulate user interactions  
✅ **Fill forms** — automate data entry  
✅ **Extract data** — scrape page content  
✅ **Inject code** — run arbitrary JavaScript  
✅ **Add shortcuts** — custom keyboard commands  
✅ **Monitor pages** — watch for changes  
✅ **Cross-domain** — work on any website  

---

## Domain Filtering

Skills can specify which sites they work on:

```javascript
const MySkill = {
  domains: ["youtube.com", "netflix.com"],
  // Only active on these domains
};
```

Or omit `domains` to work everywhere:
```javascript
const UniversalSkill = {
  // Works on all sites
};
```

---

## Advanced Features

### Async/Await Support
```javascript
handler: async (args) => {
  await someAsyncFunction();
  return { ok: true, text: "Done" };
}
```

### onPageLoad Hook
```javascript
onPageLoad: () => {
  // Runs when skill loads on page
  console.log("Skill active!");
  
  // Add global shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'p') {
      // Do something
    }
  });
}
```

### Helper Functions
```javascript
// Wait for element
const waitFor = (selector, timeout = 5000) => {
  return new Promise((resolve, reject) => {
    const el = document.querySelector(selector);
    if (el) return resolve(el);
    
    const observer = new MutationObserver(() => {
      const element = document.querySelector(selector);
      if (element) {
        observer.disconnect();
        resolve(element);
      }
    });
    
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
    
    setTimeout(() => {
      observer.disconnect();
      reject(new Error('Timeout'));
    }, timeout);
  });
};

// Use it
handler: async () => {
  const button = await waitFor('#submit-button');
  button.click();
  return { ok: true, text: "Clicked!" };
}
```

---

## Debugging Skills

1. Open DevTools Console
2. Check: `window.FridaySkills.list()` → shows loaded skills
3. Check: `window.FridaySkills.get('MySkill')` → inspect skill
4. Watch for `console.log()` from skills
5. Errors appear in console

---

## Example Skills You Can Build

1. **Social Media Automation**
   - Auto-like posts
   - Auto-follow users
   - Schedule posts
   - Bulk actions

2. **Shopping Assistants**
   - Price trackers
   - Auto-checkout
   - Coupon finders
   - Stock monitors

3. **Productivity Tools**
   - Form auto-fillers
   - Meeting note-takers
   - Email templates
   - Calendar helpers

4. **Content Tools**
   - Article readers
   - Video downloaders
   - Image extractors
   - PDF converters

5. **Developer Tools**
   - API testers
   - DOM inspectors
   - Performance monitors
   - Console enhancers

6. **Gaming Tools**
   - Auto-clickers
   - Macro recorders
   - Stats trackers
   - Bot helpers

---

## Limitations

- Skills run in content script context (not background)
- Can't access Chrome APIs directly (use background for that)
- Domain restrictions enforced by manifest
- Must reload extension after adding skills
- Some sites have CSP restrictions

---

## Best Practices

1. **Test thoroughly** before sharing
2. **Handle errors** gracefully
3. **Clear feedback** to users
4. **Respect rate limits** on APIs
5. **Don't abuse** automation
6. **Document your skills** well

---

## Sharing Skills

Skills are just JavaScript files! Share them:
- GitHub gists
- Discord/Slack
- Community forums
- Direct file sharing

Users just drop the `.js` file and reload!

---

## The Power

**YOU** asked for this exact system:
1. User asks Friday for template ✅
2. Upload to Claude ✅
3. Claude generates code ✅
4. Paste into skills folder ✅
5. Auto-loads and works ✅

**Now you can extend Friday's browser control infinitely!** 🚀

---

Questions? Check `EXTENSION_SKILL_TEMPLATE.md` for full examples.
