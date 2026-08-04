/* ============================================================
   TK Story Studio — content layer
   Style presets, prompt templates and the km/en dictionary.
   Loaded as a classic script so the app also runs from file://
   ============================================================ */
window.TK = (function () {
  'use strict';

  /* ---------- style presets ---------- */
  const STYLES = [
    { id: 's1',  thumb: 't-s1',    km: ['Social story screenshot', 'Profile + highlight + read more'], en: ['Social story screenshot', 'Profile, highlights, read more'] },
    { id: 's2',  thumb: 't-s2',    km: ['ក្រដាសរហែក + ក្លីប', 'គែមសៀវភៅ, ក្លីបប្រាក់'],              en: ['Torn paper + paperclip', 'Notebook edge, silver clip'] },
    { id: 's3',  thumb: 't-s3',    km: ['Sticky note', 'ក្រដាសលឿង, អក្សរ marker'],                   en: ['Sticky note', 'Yellow post-it, marker font'] },
    { id: 's4',  thumb: 't-s4',    km: ['វិក្កយបត្រ / សំបុត្រ', 'ក្រដាស thermal ធ្មេញ'],              en: ['Receipt / ticket', 'Perforated thermal paper'] },
    { id: 's5',  thumb: 't-s5',    km: ['Polaroid + កាវបិទ', 'រូបភាពភ្លាមៗ, washi tape'],            en: ['Polaroid + tape', 'Instant photo, washi tape'] },
    { id: 's6',  thumb: 't-s6',    km: ['ក្ដារឆ្នូត + ម្ជុល', 'កាតសន្ទស្សន៍, ម្ជុលក្រហម'],          en: ['Corkboard pin card', 'Index card, red pin'] },
    { id: 's7',  thumb: 't-s7',    km: ['Chat bubble', 'Screenshot កម្មវិធីសារ'],                     en: ['Chat bubble', 'Messaging-app screenshot'] },
    { id: 's8',  thumb: 't-s8',    km: ['កាសែតកាត់', 'ក្រដាសចាស់ រហែកគែម'],                          en: ['Newspaper clipping', 'Torn, aged newsprint'] },
    { id: 's9',  thumb: 't-s9',    km: ['Whiteboard marker', 'អក្សរសរសេរដោយ marker'],                en: ['Whiteboard marker', 'Marker handwriting'] },
    { id: 's10', thumb: 't-s10',   km: ['សំបុត្រសរសេរដៃ', 'ក្រដាសខ្សែ, អក្សរផ្ចង់'],                en: ['Handwritten letter', 'Lined paper, cursive'] },
    { id: 'thumb', thumb: 't-thumb', km: ['Website thumbnail', 'រូបភាពសម្រាប់អត្ថបទ (16:9)'],        en: ['Website thumbnail', 'Featured article image (16:9)'] }
  ];

  const STYLE_NAMES = {
    s1: 'Social story screenshot', s2: 'Torn paper + paperclip', s3: 'Sticky note',
    s4: 'Receipt / ticket',        s5: 'Polaroid + tape',        s6: 'Corkboard pin card',
    s7: 'Chat bubble',             s8: 'Newspaper clipping',     s9: 'Whiteboard marker',
    s10: 'Handwritten letter',     thumb: 'Website thumbnail'
  };

  /* ---------- static image prompts ---------- */
  const TEMPLATES = {
    s1: (t, ti, r) => `Create a vertical social-media story teaser image, ${r} aspect ratio, clean white background. Top-left: small circular profile avatar (friendly, natural lighting) next to a blurred username placeholder and a small grey "Just now" timestamp. Main post text in bold dark Roboto typography, large, left-aligned, generous line spacing:\n\n"${t}"\n\nHighlight 2-3 emotionally striking phrases in red text, and 2-3 supporting phrases with a soft translucent yellow marker highlight behind the text. Add "Read More…" in red, positioned lower-right after the text block. Footer: small dark grey text "Full story ▶" centered at the very bottom. Minimal, clean, crisp typography, no logos or watermark. Looks like a realistic screenshot of a viral social media story post.`,

    s2: (t, ti, r) => `Create a ${r} vertical image styled as a page of aged notebook paper with a torn, uneven top edge and a realistic silver paperclip clipped at the top center. Handwritten-style serif font for the main text, dark ink on cream paper:\n\n"${t}"\n\nLightly underline a few key phrases in pencil style. Bottom-right: small red handwritten-style "Read More…" note. Bottom center: small caption "Full story ▶". Warm, nostalgic paper-texture lighting, soft shadow under the paperclip.`,

    s3: (t, ti, r) => `Create a ${r} vertical image of a yellow sticky note (Post-it) with a slightly curled bottom-right corner and a small strip of tape at the top. Marker-style handwritten font, dark navy ink:\n\n"${t}"\n\nBottom-right: "Read More…" in red marker style. Bottom center small label: "Full story ▶". Soft drop shadow under the note, plain neutral desk background.`,

    s4: (t, ti, r) => `Create a ${r} vertical image styled as a thermal-printer receipt: white paper with a perforated/zig-zag top and bottom edge, thin dashed divider lines. Monospace typewriter-style font, black ink:\n\n"${t}"\n\nA dashed line before "Read More…" in bold near the bottom. Footer line: "Full story ▶" in small grey monospace text. Slight paper grain texture, minimal shadow.`,

    s5: (t, ti, r) => `Create a ${r} vertical image of an instant-photo Polaroid frame (white borders, wider bottom border) taped at two corners with washi tape at a slight angle. Below the photo area, a handwritten-style caption showing:\n\n"${t}"\n\nSmall red "Read More…" note tucked in the bottom-right corner. Small caption at the very bottom: "Full story ▶". Warm nostalgic lighting, soft film grain.`,

    s6: (t, ti, r) => `Create a ${r} vertical image of a cork-textured board background with a white index card pinned by a single red push-pin at the top center, slightly tilted. Typewriter-style text on the card:\n\n"${t}"\n\nBottom-right of the card: "Read More…" in red. Bottom center below the card: "Full story ▶" in small grey text. Moody investigative-board lighting.`,

    s7: (t, ti, r) => `Create a ${r} vertical image styled as a messaging-app screenshot (iMessage/WhatsApp style) with a single large chat bubble containing:\n\n"${t}"\n\nInclude a small timestamp above the bubble and a "Read" receipt below it. Small red "Read More…" tucked at the bottom-right of the bubble. Footer caption centered at the bottom: "Full story ▶". Clean phone-screen background, realistic UI shadows.`,

    s8: (t, ti, r) => `Create a ${r} vertical image styled as a torn newspaper clipping on slightly aged, yellowed paper with visible faint print texture and ragged edges. Bold serif headline font for the title: "${ti}". Body text in classic newspaper column serif font:\n\n"${t}"\n\nSmall red "Read More…" at the bottom-right. Footer caption: "Full story ▶" in small grey serif text at the bottom.`,

    s9: (t, ti, r) => `Create a ${r} vertical image of a clean whiteboard background with the text written in marker-style handwriting font, dark blue/black ink:\n\n"${t}"\n\nHighlight 2-3 key phrases with a marker-stroke underline in a bright accent color (orange or green). Small red "Read More…" in the bottom-right written in marker style. Footer caption centered at the bottom: "Full story ▶". Slight whiteboard glare/texture for realism.`,

    s10: (t, ti, r) => `Create a ${r} vertical image styled as a handwritten letter on lined notebook paper, with a small paperclip or wax-seal accent in a top corner. Cursive-style handwriting font, dark ink:\n\n"${t}"\n\nSmall red "Read More…" at the bottom-right in a slightly different ink color. Footer caption centered at the bottom: "Full story ▶". Warm, intimate, soft natural lighting.`,

    thumb: (t, ti, r) => `Create a ${r} website / blog featured thumbnail image illustrating the theme of this article. Editorial, photographic or soft-illustration style. Composition should work well as a small clickable thumbnail: one clear focal subject, no clutter, good contrast, warm inviting lighting, professional editorial-news look.\n\nInclude the headline as a bold caption text overlay in the lower third of the image: "${ti}" — white or high-contrast text with a subtle dark gradient/scrim behind it so it stays readable at small size, positioned like a real news-site featured-image caption.\n\nArticle theme summary to base the visual on:\n\n"${t}"\n\nNo logos or watermark.`
  };

  function buildAnimatePrompt(styleId, ratio, text, title) {
    const name = STYLE_NAMES[styleId] || 'Story image';
    return `Animate the "${name}" image into a short cinematic video clip, ${ratio} aspect ratio, 4-6 seconds, loopable.\n\nMotion: slow, subtle camera movement — a gentle Ken Burns zoom-in or soft parallax drift between foreground and background layers. Add faint floating particles or dust in the light, and a slight ambient light flicker for realism. Keep the pacing matched to the story's emotional tone below — slower and gentler for a quiet/reflective moment, a touch more energetic if the tone is upbeat or tense. Avoid anything jarring or fast-cut.\n\nBackground music: choose a track whose mood matches this story's tone — infer the right feel (e.g. melancholic piano, warm acoustic guitar, tense ambient strings, hopeful light synth) from the text below. Keep the music soft, cinematic, and non-intrusive, building gently rather than relying on a strong beat.\n\nHeadline for reference: "${title}"\nStory text for tone reference:\n\n"${text}"`;
  }

  function buildPrompt({ styleId, ratio, mode, text, title }) {
    const safeTitle = title || '(no title generated)';
    if (mode === 'animate') return buildAnimatePrompt(styleId, ratio, text, safeTitle);
    const fn = TEMPLATES[styleId] || TEMPLATES.s1;
    return fn(text, safeTitle, ratio);
  }

  /* ---------- system prompt for the generator ---------- */
  const MARK = { title: '@@TITLE@@', caption: '@@CAPTION@@', article: '@@ARTICLE@@' };

  function buildSystemPrompt(cfg) {
    return `You are a cinematic content editor. You will be given a short story text.

Rules you must follow exactly:
- Keep every sentence the user wrote exactly as-is, only fixing small grammar mistakes if needed.
- Write in the same language as the user's story text.
- Expand it into a full cinematic version of ${cfg.paraMin} to ${cfg.paraMax} paragraphs, not less than ${cfg.wordMin} words.
- Add a hook at the start, smoother transitions between paragraphs, more descriptive detail, and a strong ending.
- Paragraphs should be a bit longer, not short choppy ones.
- Also write a top viral article title, about ${cfg.titleWords} words.
- Also write a short, catchy Facebook caption (2-4 sentences) with a strong hook, written to drive clicks on the article, plus 2-3 relevant hashtags at the end.
- Do not include internal or system XML tags in your response.
- Respond in EXACTLY this plain-text format, no markdown fences, no JSON, no extra commentary:

${MARK.title}
the viral title here, one line only
${MARK.caption}
the facebook caption here, with hashtags
${MARK.article}
the full expanded article here, paragraphs separated by a blank line`;
  }

  /* ---------- i18n ---------- */
  const I18N = {
    km: {
      'a11y.skip': 'រំលងទៅមាតិកា',
      'app.tagline': 'កាត់អត្ថបទ · ពង្រីកជា Cinematic · បង្កើត AI prompt',
      'nav.studio': 'ស្ទូឌីយោ',
      'nav.visuals': 'រូបភាព',
      'nav.library': 'បណ្ណាល័យ',

      'conn.idle': 'មិនទាន់ភ្ជាប់',
      'conn.busy': 'កំពុងពិនិត្យ…',
      'conn.ok': 'ភ្ជាប់រួច',
      'conn.error': 'ភ្ជាប់មិនបាន',

      'badge.step1': 'ជំហាន ១',
      'badge.step2': 'ជំហាន ២',
      'badge.step3': 'ជំហាន ៣',
      'badge.step4': 'ជំហាន ៤',

      'studio.heading': 'សាច់រឿង → អត្ថបទ Cinematic',
      'studio.source.title': 'សាច់រឿងដើម',
      'studio.source.hint': 'រាល់ប្រយោគរបស់អ្នកត្រូវរក្សាទុកដដែល — AI គ្រាន់តែពង្រីកបន្ថែម។',
      'studio.source.placeholder': 'បិទភ្ជាប់សាច់រឿងដើមនៅទីនេះ…',
      'studio.output.title': 'លទ្ធផល',
      'studio.tuning': 'ការកំណត់ការបង្កើត',

      'cfg.paraMin': 'កថាខណ្ឌ អប្បបរមា',
      'cfg.paraMax': 'កថាខណ្ឌ អតិបរមា',
      'cfg.wordMin': 'ពាក្យ អប្បបរមា',
      'cfg.titleWords': 'ពាក្យក្នុងចំណងជើង',

      'field.title': 'ចំណងជើង Viral',
      'field.title.placeholder': 'ចំណងជើងនឹងបង្ហាញនៅទីនេះ…',
      'field.caption': 'Caption សម្រាប់ Facebook',
      'field.caption.placeholder': 'Caption នឹងបង្ហាញនៅទីនេះ…',
      'field.article': 'អត្ថបទពេញ',
      'field.article.placeholder': 'បិទភ្ជាប់អត្ថបទ ឬបង្កើតវាខាងលើ…',

      'action.generate': 'បង្កើតជា Cinematic',
      'action.stop': 'បញ្ឈប់',
      'action.copy': 'ចម្លង',
      'action.copied': 'ចម្លងរួច',
      'action.copyPrompt': 'ចម្លង Prompt',
      'action.download': 'ទាញយក .txt',
      'action.toVisuals': 'បន្តទៅរូបភាព',
      'action.close': 'បិទ',
      'action.restore': 'ស្ដារ',
      'action.delete': 'លុប',

      'visuals.heading': 'អត្ថបទកាត់ → AI image prompt',
      'visuals.trim.title': 'កាត់អត្ថបទ',
      'visuals.trim.length': 'ប្រវែង (តួអក្សរ)',
      'visuals.trim.mode': 'របៀបកាត់',
      'visuals.trim.output': 'លទ្ធផលកាត់',
      'visuals.styles.title': 'ជ្រើសរើស Style',
      'visuals.prompt.title': 'Prompt ពេញ',
      'visuals.prompt.mode': 'ប្រភេទ Prompt',
      'visuals.prompt.ratio': 'សមាមាត្រ',
      'trim.mode.sentence': 'ចុងប្រយោគ',
      'trim.mode.word': 'ចុងពាក្យ',
      'trim.mode.hard': 'តួអក្សរច្បាស់',
      'mode.static': '🖼️ រូបភាព',
      'mode.animate': '🎬 វីដេអូ + តន្ត្រី',

      'library.heading': 'ប្រវត្តិបង្កើត',
      'library.title': 'អត្ថបទដែលបានរក្សាទុក',
      'library.clear': 'លុបទាំងអស់',
      'library.empty': 'មិនទាន់មានអត្ថបទណាមួយទេ។ បង្កើតមួយនៅក្នុងស្ទូឌីយោ។',
      'library.restored': 'ស្ដារអត្ថបទរួចរាល់',
      'library.cleared': 'លុបប្រវត្តិរួចរាល់',

      'settings.title': 'ការកំណត់',
      'settings.api': 'ការតភ្ជាប់ Anthropic',
      'settings.key': 'API key',
      'settings.keyShow': 'បង្ហាញ/លាក់ key',
      'settings.connect': 'ពិនិត្យការតភ្ជាប់',
      'settings.keyHint': 'Key រក្សាទុកតែក្នុង browser របស់អ្នក (localStorage) ហើយផ្ញើទៅ Anthropic ប៉ុណ្ណោះ។ ប្រុងប្រយ័ត្ន៖ key ក្នុង client-side code មើលឃើញតាម network tab — សមរម្យសម្រាប់ tool ផ្ទាល់ខ្លួន មិនសមរម្យសម្រាប់ website សាធារណៈទេ។',
      'settings.model': 'ម៉ូដែល',
      'settings.appearance': 'រូបរាង',
      'settings.language': 'ភាសា',
      'settings.data': 'ទិន្នន័យ',
      'settings.dataHint': 'សេចក្ដីព្រាង ប្រវត្តិ និងការកំណត់ទាំងអស់ស្ថិតក្នុង browser នេះតែប៉ុណ្ណោះ។',
      'settings.clearData': 'លុបទិន្នន័យទាំងអស់',
      'settings.confirmClear': 'លុបទិន្នន័យទាំងអស់មែនទេ? សកម្មភាពនេះមិនអាចត្រឡប់វិញបានទេ។',
      'settings.cleared': 'លុបទិន្នន័យរួចរាល់',

      'theme.light': 'ភ្លឺ',
      'theme.dark': 'ងងឹត',
      'theme.system': 'ប្រព័ន្ធ',

      'msg.needKey': 'សូមបញ្ចូល Anthropic API key ក្នុងការកំណត់ជាមុនសិន',
      'msg.needStory': 'សូមបញ្ចូលសាច់រឿងជាមុនសិន',
      'msg.needArticle': 'សូមបង្កើត ឬបិទភ្ជាប់អត្ថបទជាមុនសិន',
      'msg.generating': 'កំពុងបង្កើត… សូមរង់ចាំបន្តិច',
      'msg.done': 'រួចរាល់',
      'msg.stopped': 'បានបញ្ឈប់',
      'msg.copied': 'ចម្លងរួចរាល់',
      'msg.copyFail': 'ចម្លងមិនបាន',
      'msg.empty': 'គ្មានអ្វីត្រូវចម្លងទេ',
      'msg.downloaded': 'ទាញយករួចរាល់',
      'msg.offline': 'គ្មានអ៊ីនធឺណិត — សូមពិនិត្យការតភ្ជាប់',

      'stats.words': 'ពាក្យ',
      'stats.chars': 'តួអក្សរ',
      'stats.paras': 'កថាខណ្ឌ',
      'stats.read': 'នាទីអាន',
      'stats.tokens': 'tokens',
      'stats.elapsed': 'វិនាទី'
    },

    en: {
      'a11y.skip': 'Skip to content',
      'app.tagline': 'Trim · expand to cinematic · generate AI prompts',
      'nav.studio': 'Studio',
      'nav.visuals': 'Visuals',
      'nav.library': 'Library',

      'conn.idle': 'Not connected',
      'conn.busy': 'Checking…',
      'conn.ok': 'Connected',
      'conn.error': 'Connection failed',

      'badge.step1': 'Step 1',
      'badge.step2': 'Step 2',
      'badge.step3': 'Step 3',
      'badge.step4': 'Step 4',

      'studio.heading': 'Story → cinematic article',
      'studio.source.title': 'Raw story',
      'studio.source.hint': 'Every sentence you wrote is kept as-is — the AI only expands around it.',
      'studio.source.placeholder': 'Paste your raw story text here…',
      'studio.output.title': 'Results',
      'studio.tuning': 'Generation settings',

      'cfg.paraMin': 'Paragraphs min',
      'cfg.paraMax': 'Paragraphs max',
      'cfg.wordMin': 'Min words',
      'cfg.titleWords': 'Title words',

      'field.title': 'Viral title',
      'field.title.placeholder': 'The generated title appears here…',
      'field.caption': 'Facebook caption',
      'field.caption.placeholder': 'The generated caption appears here…',
      'field.article': 'Full article',
      'field.article.placeholder': 'Paste an article, or generate one above…',

      'action.generate': 'Generate cinematic',
      'action.stop': 'Stop',
      'action.copy': 'Copy',
      'action.copied': 'Copied',
      'action.copyPrompt': 'Copy prompt',
      'action.download': 'Download .txt',
      'action.toVisuals': 'Continue to visuals',
      'action.close': 'Close',
      'action.restore': 'Restore',
      'action.delete': 'Delete',

      'visuals.heading': 'Trimmed text → AI image prompt',
      'visuals.trim.title': 'Trim',
      'visuals.trim.length': 'Length (characters)',
      'visuals.trim.mode': 'Cut at',
      'visuals.trim.output': 'Trimmed output',
      'visuals.styles.title': 'Choose a style',
      'visuals.prompt.title': 'Full prompt',
      'visuals.prompt.mode': 'Prompt type',
      'visuals.prompt.ratio': 'Aspect ratio',
      'trim.mode.sentence': 'Sentence end',
      'trim.mode.word': 'Word boundary',
      'trim.mode.hard': 'Exact characters',
      'mode.static': '🖼️ Static image',
      'mode.animate': '🎬 Animate + music',

      'library.heading': 'Generation history',
      'library.title': 'Saved articles',
      'library.clear': 'Clear all',
      'library.empty': 'Nothing saved yet. Generate an article in the Studio.',
      'library.restored': 'Article restored',
      'library.cleared': 'History cleared',

      'settings.title': 'Settings',
      'settings.api': 'Anthropic connection',
      'settings.key': 'API key',
      'settings.keyShow': 'Show/hide key',
      'settings.connect': 'Test connection',
      'settings.keyHint': 'The key is stored only in this browser (localStorage) and is sent to Anthropic only. Caution: a key in client-side code is visible in the network tab — fine for your own tool, not safe for a public website.',
      'settings.model': 'Model',
      'settings.appearance': 'Appearance',
      'settings.language': 'Language',
      'settings.data': 'Data',
      'settings.dataHint': 'Drafts, history and settings live in this browser only.',
      'settings.clearData': 'Clear all local data',
      'settings.confirmClear': 'Clear all local data? This cannot be undone.',
      'settings.cleared': 'Local data cleared',

      'theme.light': 'Light',
      'theme.dark': 'Dark',
      'theme.system': 'System',

      'msg.needKey': 'Add your Anthropic API key in Settings first',
      'msg.needStory': 'Paste a story first',
      'msg.needArticle': 'Generate or paste an article first',
      'msg.generating': 'Generating… this can take a moment',
      'msg.done': 'Done',
      'msg.stopped': 'Stopped',
      'msg.copied': 'Copied',
      'msg.copyFail': 'Could not copy',
      'msg.empty': 'Nothing to copy',
      'msg.downloaded': 'Downloaded',
      'msg.offline': 'You are offline — check your connection',

      'stats.words': 'words',
      'stats.chars': 'chars',
      'stats.paras': 'paragraphs',
      'stats.read': 'min read',
      'stats.tokens': 'tokens',
      'stats.elapsed': 's'
    }
  };

  /* ---------- model capabilities ---------- */
  /* effort + adaptive thinking exist on the 5-series; Haiku 4.5 rejects `effort`. */
  const MODELS = {
    'claude-opus-5':   { effort: 'medium', adaptiveThinking: true,  maxTokens: 32000,
                         hint: { km: 'គុណភាពខ្ពស់បំផុត សម្រាប់អត្ថបទវែង និងស៊ីជម្រៅ។',
                                 en: 'Highest quality — best for long, layered articles.' } },
    'claude-sonnet-5': { effort: 'medium', adaptiveThinking: true,  maxTokens: 32000,
                         hint: { km: 'លំនឹងល្អរវាងគុណភាព ល្បឿន និងតម្លៃ។',
                                 en: 'A strong balance of quality, speed and cost.' } },
    'claude-haiku-4-5':{ effort: null,     adaptiveThinking: false, maxTokens: 16000,
                         hint: { km: 'លឿននិងថោកបំផុត សម្រាប់សាច់រឿងខ្លី។',
                                 en: 'Fastest and cheapest — good for short stories.' } }
  };

  return { STYLES, STYLE_NAMES, TEMPLATES, MODELS, I18N, MARK, buildPrompt, buildSystemPrompt };
})();
