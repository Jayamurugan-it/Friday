# Friday Extension Skills — Browser Automation Template

**Drop any `.js` file in `extension/skills/` folder and Friday auto-loads it.**

Extension skills run **inside the browser** and can interact with any website.

---

## Basic Structure

Every extension skill must export:

```javascript
// extension/skills/my_skill.js

window.FridaySkills = window.FridaySkills || {};

window.FridaySkills.my_skill = {
  // Skill metadata
  name: "My Skill",
  description: "What this skill does",
  
  // Which websites this skill works on
  // Use "*" for all sites, or specific domains
  domains: ["youtube.com", "music.youtube.com"],
  
  // Commands this skill provides
  commands: {
    
    play: function() {
      // Find play button and click it
      const playBtn = document.querySelector('.ytp-play-button');
      if (playBtn) {
        playBtn.click();
        return { ok: true, message: "Playing" };
      }
      return { ok: false, message: "Play button not found" };
    },
    
    pause: function() {
      const pauseBtn = document.querySelector('.ytp-play-button');
      if (pauseBtn) {
        pauseBtn.click();
        return { ok: true, message: "Paused" };
      }
      return { ok: false, message: "Pause button not found" };
    }
  }
};
```

Now users can say: **"Friday, youtube play"** or **"Friday, youtube pause"**

---

## Return Format

Commands must return:
```javascript
{
  ok: true,           // Success status
  message: "Done",    // Output shown to user
  data: {...}         // Optional: extra data
}
```

---

## Complete Example: YouTube Controller

```javascript
// extension/skills/youtube_skill.js

window.FridaySkills = window.FridaySkills || {};

window.FridaySkills.youtube = {
  name: "YouTube Controller",
  description: "Control YouTube videos with voice commands",
  domains: ["youtube.com", "music.youtube.com"],
  
  commands: {
    
    play: function() {
      const video = document.querySelector('video');
      if (video) {
        video.play();
        return { ok: true, message: "▶ Playing" };
      }
      return { ok: false, message: "No video found" };
    },
    
    pause: function() {
      const video = document.querySelector('video');
      if (video) {
        video.pause();
        return { ok: true, message: "⏸ Paused" };
      }
      return { ok: false, message: "No video found" };
    },
    
    resume: function() {
      return this.play();
    },
    
    mute: function() {
      const video = document.querySelector('video');
      if (video) {
        video.muted = true;
        return { ok: true, message: "🔇 Muted" };
      }
      return { ok: false, message: "No video found" };
    },
    
    unmute: function() {
      const video = document.querySelector('video');
      if (video) {
        video.muted = false;
        return { ok: true, message: "🔊 Unmuted" };
      }
      return { ok: false, message: "No video found" };
    },
    
    volume: function(level) {
      const video = document.querySelector('video');
      if (video) {
        video.volume = Math.max(0, Math.min(1, level / 100));
        return { ok: true, message: `🔊 Volume: ${level}%` };
      }
      return { ok: false, message: "No video found" };
    },
    
    speed: function(rate) {
      const video = document.querySelector('video');
      if (video) {
        video.playbackRate = rate;
        return { ok: true, message: `⚡ Speed: ${rate}x` };
      }
      return { ok: false, message: "No video found" };
    },
    
    skip: function(seconds) {
      const video = document.querySelector('video');
      if (video) {
        video.currentTime += seconds;
        return { ok: true, message: `⏩ Skipped ${seconds}s` };
      }
      return { ok: false, message: "No video found" };
    },
    
    back: function(seconds) {
      const video = document.querySelector('video');
      if (video) {
        video.currentTime -= seconds;
        return { ok: true, message: `⏪ Back ${seconds}s` };
      }
      return { ok: false, message: "No video found" };
    },
    
    fullscreen: function() {
      const video = document.querySelector('video');
      if (video) {
        if (video.requestFullscreen) video.requestFullscreen();
        else if (video.webkitRequestFullscreen) video.webkitRequestFullscreen();
        return { ok: true, message: "⛶ Fullscreen" };
      }
      return { ok: false, message: "No video found" };
    },
    
    info: function() {
      const video = document.querySelector('video');
      if (!video) {
        return { ok: false, message: "No video found" };
      }
      
      const current = Math.floor(video.currentTime);
      const duration = Math.floor(video.duration);
      const mins = Math.floor(current / 60);
      const secs = current % 60;
      const totalMins = Math.floor(duration / 60);
      const totalSecs = duration % 60;
      
      return {
        ok: true,
        message: `${video.paused ? '⏸' : '▶'} ${mins}:${secs.toString().padStart(2,'0')} / ${totalMins}:${totalSecs.toString().padStart(2,'0')} | Vol: ${Math.round(video.volume*100)}% | Speed: ${video.playbackRate}x`,
        data: {
          playing: !video.paused,
          currentTime: video.currentTime,
          duration: video.duration,
          volume: video.volume,
          speed: video.playbackRate
        }
      };
    }
  }
};
```

**Usage:**
```
Friday, youtube play
Friday, youtube pause
Friday, youtube volume 50
Friday, youtube speed 1.5
Friday, youtube skip 10
Friday, youtube info
```

---

## Example: Spotify Controller

```javascript
// extension/skills/spotify_skill.js

window.FridaySkills = window.FridaySkills || {};

window.FridaySkills.spotify = {
  name: "Spotify Controller",
  description: "Control Spotify web player",
  domains: ["open.spotify.com"],
  
  commands: {
    
    play: function() {
      const btn = document.querySelector('[data-testid="control-button-play"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "▶ Playing" };
      }
      return { ok: false, message: "Play button not found" };
    },
    
    pause: function() {
      const btn = document.querySelector('[data-testid="control-button-pause"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "⏸ Paused" };
      }
      return { ok: false, message: "Pause button not found" };
    },
    
    next: function() {
      const btn = document.querySelector('[data-testid="control-button-skip-forward"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "⏭ Next track" };
      }
      return { ok: false, message: "Next button not found" };
    },
    
    previous: function() {
      const btn = document.querySelector('[data-testid="control-button-skip-back"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "⏮ Previous track" };
      }
      return { ok: false, message: "Previous button not found" };
    },
    
    shuffle: function() {
      const btn = document.querySelector('[data-testid="control-button-shuffle"]');
      if (btn) {
        btn.click();
        const active = btn.classList.contains('active');
        return { ok: true, message: active ? "🔀 Shuffle on" : "➡ Shuffle off" };
      }
      return { ok: false, message: "Shuffle button not found" };
    },
    
    nowPlaying: function() {
      const title = document.querySelector('[data-testid="context-item-link"]');
      const artist = document.querySelector('[data-testid="context-item-info-artist"]');
      
      if (title && artist) {
        return {
          ok: true,
          message: `🎵 ${title.textContent} - ${artist.textContent}`,
          data: { title: title.textContent, artist: artist.textContent }
        };
      }
      return { ok: false, message: "No track playing" };
    }
  }
};
```

---

## Example: Gmail Controller

```javascript
// extension/skills/gmail_skill.js

window.FridaySkills = window.FridaySkills || {};

window.FridaySkills.gmail = {
  name: "Gmail Controller",
  description: "Control Gmail interface",
  domains: ["mail.google.com"],
  
  commands: {
    
    compose: function() {
      const btn = document.querySelector('[gh="cm"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "✉ Compose opened" };
      }
      return { ok: false, message: "Compose button not found" };
    },
    
    search: function(query) {
      const searchBox = document.querySelector('input[aria-label="Search mail"]');
      if (searchBox) {
        searchBox.value = query;
        searchBox.dispatchEvent(new Event('input', { bubbles: true }));
        searchBox.form.submit();
        return { ok: true, message: `🔍 Searching: ${query}` };
      }
      return { ok: false, message: "Search box not found" };
    },
    
    unreadCount: function() {
      const badge = document.querySelector('.aim');
      if (badge) {
        const count = badge.textContent;
        return { ok: true, message: `📬 ${count} unread`, data: { count } };
      }
      return { ok: true, message: "📭 No unread emails" };
    },
    
    refresh: function() {
      const btn = document.querySelector('[gh="tm"] button[aria-label*="Refresh"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "🔄 Refreshed" };
      }
      return { ok: false, message: "Refresh button not found" };
    },
    
    archive: function() {
      const btn = document.querySelector('[data-tooltip="Archive"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "📦 Archived" };
      }
      return { ok: false, message: "Archive button not found (select an email first)" };
    },
    
    delete: function() {
      const btn = document.querySelector('[data-tooltip="Delete"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "🗑 Deleted" };
      }
      return { ok: false, message: "Delete button not found (select an email first)" };
    }
  }
};
```

---

## Example: Twitter/X Controller

```javascript
// extension/skills/twitter_skill.js

window.FridaySkills = window.FridaySkills || {};

window.FridaySkills.twitter = {
  name: "Twitter/X Controller",
  description: "Control Twitter/X interface",
  domains: ["twitter.com", "x.com"],
  
  commands: {
    
    compose: function() {
      const btn = document.querySelector('[data-testid="SideNav_NewTweet_Button"]');
      if (btn) {
        btn.click();
        return { ok: true, message: "✍ Compose tweet opened" };
      }
      return { ok: false, message: "Compose button not found" };
    },
    
    post: function(text) {
      // Find compose if not open
      this.compose();
      
      setTimeout(() => {
        const textArea = document.querySelector('[data-testid="tweetTextarea_0"]');
        if (textArea) {
          textArea.textContent = text;
          textArea.dispatchEvent(new Event('input', { bubbles: true }));
          
          // Find and click tweet button
          setTimeout(() => {
            const tweetBtn = document.querySelector('[data-testid="tweetButtonInline"]');
            if (tweetBtn && !tweetBtn.disabled) {
              tweetBtn.click();
              return { ok: true, message: `🐦 Posted: ${text.slice(0, 50)}` };
            }
          }, 500);
        }
      }, 1000);
      
      return { ok: true, message: "Posting tweet..." };
    },
    
    like: function() {
      // Like the first visible tweet
      const likeBtn = document.querySelector('[data-testid="like"]:not([data-testid*="unlike"])');
      if (likeBtn) {
        likeBtn.click();
        return { ok: true, message: "❤️ Liked" };
      }
      return { ok: false, message: "No tweet to like" };
    },
    
    retweet: function() {
      const retweetBtn = document.querySelector('[data-testid="retweet"]');
      if (retweetBtn) {
        retweetBtn.click();
        // Confirm retweet
        setTimeout(() => {
          const confirm = document.querySelector('[data-testid="retweetConfirm"]');
          if (confirm) confirm.click();
        }, 300);
        return { ok: true, message: "🔄 Retweeted" };
      }
      return { ok: false, message: "No tweet to retweet" };
    },
    
    search: function(query) {
      const searchBox = document.querySelector('[data-testid="SearchBox_Search_Input"]');
      if (searchBox) {
        searchBox.value = query;
        searchBox.dispatchEvent(new Event('input', { bubbles: true }));
        searchBox.form.submit();
        return { ok: true, message: `🔍 Searching: ${query}` };
      }
      return { ok: false, message: "Search box not found" };
    }
  }
};
```

---

## Advanced: With State Management

```javascript
// extension/skills/notes_skill.js

window.FridaySkills = window.FridaySkills || {};

window.FridaySkills.notes = {
  name: "Page Notes",
  description: "Take notes on any page",
  domains: ["*"],  // Works on all sites
  
  // Skill can maintain state
  state: {
    notes: {}  // URL -> note text
  },
  
  commands: {
    
    save: function(note) {
      const url = window.location.href;
      this.state.notes[url] = note;
      
      // Save to localStorage
      localStorage.setItem('friday_notes', JSON.stringify(this.state.notes));
      
      return { ok: true, message: `📝 Note saved for this page` };
    },
    
    read: function() {
      const url = window.location.href;
      const note = this.state.notes[url];
      
      if (note) {
        return { ok: true, message: `📝 Note: ${note}`, data: { note } };
      }
      return { ok: false, message: "No note for this page" };
    },
    
    clear: function() {
      const url = window.location.href;
      delete this.state.notes[url];
      localStorage.setItem('friday_notes', JSON.stringify(this.state.notes));
      return { ok: true, message: "🗑 Note cleared" };
    },
    
    list: function() {
      const urls = Object.keys(this.state.notes);
      if (urls.length === 0) {
        return { ok: true, message: "No notes saved" };
      }
      
      const lines = urls.map(url => {
        const shortUrl = url.length > 50 ? url.slice(0, 50) + '...' : url;
        return `${shortUrl}: ${this.state.notes[url].slice(0, 30)}...`;
      });
      
      return { ok: true, message: `📝 Notes (${urls.length}):\n${lines.join('\n')}` };
    }
  },
  
  // Initialize state on load
  init: function() {
    const saved = localStorage.getItem('friday_notes');
    if (saved) {
      this.state.notes = JSON.parse(saved);
    }
  }
};

// Auto-initialize
window.FridaySkills.notes.init();
```

---

## Helper Functions Available

Inside your skill commands, you can use:

```javascript
// Sleep/wait
const sleep = ms => new Promise(r => setTimeout(r, ms));
await sleep(1000);

// Query elements safely
const el = document.querySelector('.my-selector');
if (!el) return { ok: false, message: "Element not found" };

// Trigger events properly (for React/Vue apps)
function dispatchChange(element) {
  ['input', 'change', 'keyup', 'blur'].forEach(evt => {
    element.dispatchEvent(new Event(evt, { bubbles: true }));
  });
}

// Check if element is visible
function isVisible(el) {
  return el && el.offsetParent !== null;
}

// Wait for element to appear
async function waitForElement(selector, timeout = 5000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const el = document.querySelector(selector);
    if (el) return el;
    await sleep(100);
  }
  return null;
}
```

---

## Command Naming

Users say: `"Friday, [skill_name] [command] [args]"`

Examples:
- `"Friday, youtube play"` → calls `youtube.commands.play()`
- `"Friday, youtube volume 50"` → calls `youtube.commands.volume(50)`
- `"Friday, spotify next"` → calls `spotify.commands.next()`
- `"Friday, gmail search project alpha"` → calls `gmail.commands.search("project alpha")`

Friday automatically parses arguments from natural language!

---

## Testing Your Skill

1. Save skill to `extension/skills/my_skill.js`
2. Reload extension in Chrome
3. Navigate to a matching domain
4. Open console: `window.FridaySkills` should show your skill
5. Test: `"Friday, [your command]"`

---

## Best Practices

1. **Domain specific**: Use specific domains, not "*" unless truly universal
2. **Error handling**: Always check if elements exist before interacting
3. **User feedback**: Return clear messages about what happened
4. **Timing**: Use `await sleep()` if elements need time to load
5. **Event dispatching**: Use proper events for React/Vue/Angular apps
6. **State persistence**: Use localStorage for data that should survive page reloads

---

## Debugging

```javascript
commands: {
  test: function() {
    console.log('Friday skill running!');
    console.log('Current page:', window.location.href);
    console.log('Skill state:', this.state);
    return { ok: true, message: "Check console for debug info" };
  }
}
```

---

**Questions?** Say `"Friday, extension skill help"` or check examples in `extension/skills/`

**Share your skills:** Export `.js` files and share with other Friday users!
