<?php
/**
 * The TK Article panel markup, rendered via edit_form_top.
 *
 * @var WP_Post $post
 */
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
?>
<div id="tk-article-panel" class="tk-article-panel">
	<div class="tk-article-header">
		<span class="tk-article-logo">TK</span>
		<div class="tk-article-heading">
			<h2><?php esc_html_e( 'TK Article', 'tk-article' ); ?></h2>
			<p><?php esc_html_e( 'Turn your own draft or your own YouTube video into a ready-to-edit post.', 'tk-article' ); ?></p>
		</div>
	</div>

	<div class="tk-article-tabs" role="tablist">
		<button type="button" class="tk-article-tab is-active" data-tab="content" role="tab"><?php esc_html_e( 'My Content', 'tk-article' ); ?></button>
		<button type="button" class="tk-article-tab" data-tab="youtube" role="tab"><?php esc_html_e( 'YouTube Video', 'tk-article' ); ?></button>
	</div>

	<div class="tk-article-panels">
		<div class="tk-article-tabpanel is-active" data-panel="content">
			<div class="tk-article-subtoggle">
				<button type="button" class="tk-article-subtab is-active" data-mode="paste"><?php esc_html_e( 'Paste Draft', 'tk-article' ); ?></button>
				<button type="button" class="tk-article-subtab" data-mode="url"><?php esc_html_e( 'Import My URL', 'tk-article' ); ?></button>
			</div>

			<div class="tk-article-mode is-active" data-mode-panel="paste">
				<label class="tk-article-label" for="tk-article-paste-title"><?php esc_html_e( 'Title', 'tk-article' ); ?></label>
				<input type="text" id="tk-article-paste-title" class="tk-article-input" placeholder="<?php esc_attr_e( 'Your article title…', 'tk-article' ); ?>" />

				<label class="tk-article-label" for="tk-article-paste-body"><?php esc_html_e( 'Content', 'tk-article' ); ?></label>
				<textarea id="tk-article-paste-body" class="tk-article-textarea" rows="8" placeholder="<?php esc_attr_e( 'Paste your own draft text or HTML here…', 'tk-article' ); ?>"></textarea>

				<label class="tk-article-label" for="tk-article-paste-image"><?php esc_html_e( 'Featured image URL (optional)', 'tk-article' ); ?></label>
				<input type="url" id="tk-article-paste-image" class="tk-article-input" placeholder="https://…" />

				<button type="button" id="tk-article-load-paste" class="tk-article-btn tk-article-btn-primary">
					<?php esc_html_e( 'Load into Editor', 'tk-article' ); ?>
				</button>
			</div>

			<div class="tk-article-mode" data-mode-panel="url">
				<label class="tk-article-label" for="tk-article-url"><?php esc_html_e( 'Page URL', 'tk-article' ); ?></label>
				<div class="tk-article-inline">
					<input type="url" id="tk-article-url" class="tk-article-input" placeholder="https://your-own-site.com/your-article" />
					<button type="button" id="tk-article-fetch-url" class="tk-article-btn tk-article-btn-primary"><?php esc_html_e( 'Fetch Content', 'tk-article' ); ?></button>
				</div>
				<p class="tk-article-hint"><?php esc_html_e( 'Use a page you own or have permission to republish — this imports its title, text and image straight into the editor.', 'tk-article' ); ?></p>
			</div>
		</div>

		<div class="tk-article-tabpanel" data-panel="youtube">
			<label class="tk-article-label" for="tk-article-yt-url"><?php esc_html_e( 'Your YouTube Video URL', 'tk-article' ); ?></label>
			<div class="tk-article-inline">
				<input type="url" id="tk-article-yt-url" class="tk-article-input" placeholder="https://www.youtube.com/watch?v=…" />
				<button type="button" id="tk-article-generate-yt" class="tk-article-btn tk-article-btn-primary"><?php esc_html_e( 'Generate Post', 'tk-article' ); ?></button>
			</div>
			<p class="tk-article-hint"><?php esc_html_e( 'Paste the link to your own video. TK Article drafts a post from its title, description and captions, embeds the video, and sets its thumbnail as the featured image.', 'tk-article' ); ?></p>
		</div>
	</div>

	<div id="tk-article-status" class="tk-article-status" hidden></div>

	<div class="tk-article-toolbar">
		<span class="tk-article-toolbar-label"><?php esc_html_e( 'AI Tools', 'tk-article' ); ?></span>
		<button type="button" class="tk-article-btn" id="tk-article-rewrite-title" disabled>✨ <?php esc_html_e( 'Rewrite Title', 'tk-article' ); ?></button>
		<button type="button" class="tk-article-btn" id="tk-article-improve-content" disabled>🪄 <?php esc_html_e( 'Improve Content', 'tk-article' ); ?></button>
		<button type="button" class="tk-article-btn" id="tk-article-reformat-content" disabled>🧹 <?php esc_html_e( 'Re-format Content', 'tk-article' ); ?></button>
		<button type="button" class="tk-article-btn" id="tk-article-fb-caption" disabled>📘 <?php esc_html_e( 'Gen FB Caption', 'tk-article' ); ?></button>
		<button type="button" class="tk-article-btn" id="tk-article-download-thumb" disabled>📥 <?php esc_html_e( 'Download Thumbnail', 'tk-article' ); ?></button>
	</div>

	<div id="tk-article-caption-output" class="tk-article-caption-output" hidden>
		<label class="tk-article-label" for="tk-article-caption-text"><?php esc_html_e( 'Facebook Caption', 'tk-article' ); ?></label>
		<textarea id="tk-article-caption-text" class="tk-article-textarea" rows="4" readonly></textarea>
	</div>

	<div class="tk-article-footer">
		<span><?php esc_html_e( 'TK Article', 'tk-article' ); ?> · v<?php echo esc_html( TK_ARTICLE_VERSION ); ?></span>
		<a href="<?php echo esc_url( admin_url( 'options-general.php?page=tk-article' ) ); ?>"><?php esc_html_e( 'Settings', 'tk-article' ); ?></a>
	</div>
</div>
