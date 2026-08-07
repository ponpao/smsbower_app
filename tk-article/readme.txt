=== TK Article ===
Contributors: tk
Tags: content, ai, youtube, editor
Requires at least: 5.8
Tested up to: 6.6
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

AI-assisted writing panel for the Add Post screen — turn your own draft or your own YouTube video into a polished, ready-to-edit post.

== Description ==

TK Article adds a panel above the title field on Add/Edit Post with two ways to start a draft:

* **My Content** — paste your own draft text, or import a page you own/have rights to publish (pulls its title, text and image into the editor).
* **YouTube Video** — paste the link to your own video; TK Article drafts a post from its title, description and captions, embeds the video, and sets its thumbnail as the featured image.

Once content is in the editor, use the AI toolbar to:

* ✨ Rewrite Title
* 🪄 Improve Content
* 🧹 Re-format Content
* 📘 Gen FB Caption
* 📥 Download Thumbnail

Requires an OpenAI-compatible API key, set under Settings → TK Article.

== Installation ==

1. Upload the `tk-article` folder to `/wp-content/plugins/`.
2. Activate the plugin through the "Plugins" menu in WordPress.
3. Go to Settings → TK Article and add your AI API key.
4. Go to Posts → Add New — the TK Article panel appears above the title field.

== Frequently Asked Questions ==

= Does this fetch content from other people's websites? =

The URL importer is meant for pages you own or have permission to republish. It does not attempt to bypass paywalls, robots.txt, or any access restriction.

= Which AI provider does it use? =

Any OpenAI-compatible chat-completions endpoint. Set the API key and model name in Settings → TK Article.

== Changelog ==

= 1.0.0 =
* Initial release: My Content (paste/import), YouTube Video generator, AI toolbar, content protection setting.
