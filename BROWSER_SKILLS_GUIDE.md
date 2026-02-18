# Friday Browser Skills — Quick Guide

**Control ANY website with Friday using JavaScript skills!**

---

## The Complete Workflow

### 1. Get Template
```
Friday, show extension skill template
```
Opens `EXTENSION_SKILL_TEMPLATE.md` with 5 complete examples.

### 2. Create Skill
Upload template to Claude.ai and say:
```
Write me a [Website] controller skill that can:
- [Feature 1]
- [Feature 2]
- [Feature 3]
```

**Examples:**
- "Write me a Netflix controller: play/pause/next episode"
- "Write me a Spotify skill: play/pause/next/shuffle"
- "Write me a Gmail skill: compose/search/archive"
- "Write me an Amazon skill: add to cart/checkout"

### 3. Install Skill
1. Save generated code as `extension/skills/[name]_skill.js`
2. Reload Friday extension in Chrome
3. Navigate to the website
4. Ready!

### 4. Use Skill
```
Friday, [skillname] [command]
```

---

## Built-in Example: YouTube

Friday includes a complete YouTube controller.

**Try these commands on any YouTube page:**

```bash
# Playback
Friday, youtube play
Friday, youtube pause
Friday, youtube resume
Friday, youtube stop

# Volume
Friday, youtube mute
Friday, youtube unmute
Friday, youtube volume 50
Friday, youtube volume 100

# Seek
Friday, youtube skip 10
Friday, youtube back 5
Friday, youtube restart

# Speed
Friday, youtube speed 1.5
Friday, youtube speed 2

# Actions
Friday, youtube fullscreen
Friday, youtube next
Friday, youtube like
Friday, youtube subscribe

# Info
Friday, youtube info
```

**All of this works because:**
1. YouTube skill is in `extension/skills/youtube_skill.js`
2. Content script loads it automatically
3. Friday maps commands to JavaScript functions
4. Functions interact with YouTube's DOM

---

## How It Works

### Skill Structure

```javascript
// extension/skills/my_skill.js

window.FridaySkills = window.FridaySkills || {};

window.FridaySkills.skillname = {
  name: "My Skill",
  description: "What it does",
  domains: ["example.com"],  // Which sites it works on
  
  commands: {
    play: function() {
      // Find play button
      const btn = document.querySelector('.play-button');
      if (btn) {
        btn.click();
        return { ok: true, message: "Playing" };
      }
      return { ok: false, message: "Button not found" };
    }
  }
};
```

### Command Flow

1. User: "Friday, youtube play"
2. Friday Python agent → `youtube_play()` tool
3. Tool → Flask server → `skill:youtube:play` command
4. Extension polls Flask → gets command
5. Content script → `executeExtensionSkill("youtube", "play")`
6. Skill function → clicks play button
7. Result → back to Friday → shown to user

---

## Real Use Cases

### Netflix
```javascript
// extension/skills/netflix_skill.js
commands: {
  play: () => document.querySelector('.watch-video').click(),
  nextEpisode: () => document.querySelector('.next-episode').click(),
  // ...
}
```

```bash
Friday, netflix play
Friday, netflix next episode
```

### Gmail
```javascript
commands: {
  compose: () => document.querySelector('[gh="cm"]').click(),
  search: (query) => {
    const box = document.querySelector('input[aria-label="Search mail"]');
    box.value = query;
    box.form.submit();
  }
}
```

```bash
Friday, gmail compose
Friday, gmail search project alpha
```

### Twitter/X
```javascript
commands: {
  post: (text) => {
    // Open compose
    document.querySelector('[data-testid="SideNav_NewTweet_Button"]').click();
    // Type text
    setTimeout(() => {
      document.querySelector('[data-testid="tweetTextarea_0"]').textContent = text;
    }, 1000);
  }
}
```

```bash
Friday, twitter post "Hello from Friday AI!"
```

---

## Skill Can Do ANYTHING

Because skills run as content scripts with full DOM access, they can:

✅ Click buttons/links  
✅ Fill forms  
✅ Read page content  
✅ Control video/audio players  
✅ Access localStorage/cookies  
✅ Modify page styles  
✅ Inject elements  
✅ Listen to events  
✅ Call page JavaScript functions  
✅ Everything a user can do manually  

---

## Multiple Skills

You can have unlimited skills. Examples:

```
extension/skills/
├── youtube_skill.js      (built-in)
├── netflix_skill.js      (you create)
├── spotify_skill.js      (you create)
├── gmail_skill.js        (you create)
├── twitter_skill.js      (you create)
├── amazon_skill.js       (you create)
└── custom_notes.js       (works everywhere)
```

Each skill registers commands independently.

---

## Domain Matching

```javascript
domains: ["youtube.com"]           // Only YouTube
domains: ["*.google.com"]          // Any Google domain
domains: ["example.com", "ex.com"] // Multiple domains
domains: ["*"]                     // ALL sites (use carefully)
```

Friday checks the current page's domain before executing skill commands.

---

## Advanced: Skills with State

```javascript
window.FridaySkills.notes = {
  domains: ["*"],
  
  state: {
    notes: {}  // Persists during session
  },
  
  commands: {
    save: function(text) {
      this.state.notes[window.location.href] = text;
      localStorage.setItem('friday_notes', JSON.stringify(this.state.notes));
      return { ok: true, message: "Note saved" };
    },
    
    read: function() {
      const note = this.state.notes[window.location.href];
      return note ? 
        { ok: true, message: note } : 
        { ok: false, message: "No note for this page" };
    }
  }
};
```

---

## Debugging

1. **Check skill loaded:**
   ```javascript
   // In browser console
   console.log(window.FridaySkills);
   ```

2. **Test skill directly:**
   ```javascript
   window.FridaySkills.youtube.commands.play();
   ```

3. **Add console logs:**
   ```javascript
   commands: {
     play: function() {
       console.log('Friday: YouTube play called');
       // ... rest of code
     }
   }
   ```

---

## Tips

1. **Use specific selectors** — `document.querySelector('.play-btn')` is better than complex XPath
2. **Wait for elements** — some sites load slowly, use `await sleep(1000)`
3. **Dispatch events** — React/Vue apps need proper event dispatch
4. **Test manually first** — open console, test selectors before writing skill
5. **Check domains** — skill only runs on specified domains
6. **Return clear messages** — users see the `message` field

---

## Template Reference

Full template with examples: `EXTENSION_SKILL_TEMPLATE.md`

Includes complete working code for:
1. YouTube (built-in)
2. Spotify
3. Gmail
4. Twitter/X
5. Universal page notes

---

## FAQ

**Q: Can skills call Friday's Python tools?**  
A: Not directly. Skills run in browser. But you can trigger Python via:
- User says "Friday, [command]" → Python executes → calls skill
- Skills can make fetch() requests to Flask server

**Q: Can I use npm packages?**  
A: No, skills are pure JavaScript loaded as content scripts. Use CDN imports if needed.

**Q: Do skills persist between sessions?**  
A: Skill code persists (it's a file). Skill state (variables) resets on page reload unless you use localStorage.

**Q: Can I share skills?**  
A: Yes! Just share the `.js` file. Anyone can drop it in their `extension/skills/` folder.

**Q: How many skills can I have?**  
A: Unlimited. Each skill adds minimal overhead.

---

**Go create skills for YOUR favorite websites!** 🚀
