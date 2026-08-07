<?php
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Renders the panel above the title field on Add/Edit Post, the Settings
 * page under Settings → TK Article, and enqueues admin-only assets.
 */
class TK_Article_Admin {

	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'edit_form_top', array( $this, 'render_panel' ) );
		add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_assets' ) );
		add_action( 'admin_menu', array( $this, 'register_settings_page' ) );
		add_action( 'admin_init', array( $this, 'register_settings' ) );
	}

	public function register_settings_page() {
		add_options_page(
			__( 'TK Article', 'tk-article' ),
			__( 'TK Article', 'tk-article' ),
			'manage_options',
			'tk-article',
			array( $this, 'render_settings_page' )
		);
	}

	public function register_settings() {
		register_setting(
			'tk_article_settings',
			'tk_article_api_key',
			array(
				'sanitize_callback' => 'sanitize_text_field',
				'default'           => '',
			)
		);
		register_setting(
			'tk_article_settings',
			'tk_article_ai_model',
			array(
				'sanitize_callback' => 'sanitize_text_field',
				'default'           => 'gpt-4o-mini',
			)
		);
		register_setting(
			'tk_article_settings',
			'tk_article_content_protection',
			array(
				'sanitize_callback' => 'absint',
				'default'           => 0,
			)
		);
	}

	public function render_settings_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		?>
		<div class="wrap tk-article-settings">
			<h1><?php esc_html_e( 'TK Article Settings', 'tk-article' ); ?></h1>
			<form method="post" action="options.php">
				<?php settings_fields( 'tk_article_settings' ); ?>
				<table class="form-table" role="presentation">
					<tr>
						<th scope="row"><label for="tk_article_api_key"><?php esc_html_e( 'AI API Key', 'tk-article' ); ?></label></th>
						<td>
							<input type="password" id="tk_article_api_key" name="tk_article_api_key" value="<?php echo esc_attr( get_option( 'tk_article_api_key', '' ) ); ?>" class="regular-text" autocomplete="off" />
							<p class="description"><?php esc_html_e( 'OpenAI-compatible API key, used by Rewrite Title / Improve Content / Re-format / FB Caption and the YouTube post generator.', 'tk-article' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="tk_article_ai_model"><?php esc_html_e( 'AI Model', 'tk-article' ); ?></label></th>
						<td>
							<input type="text" id="tk_article_ai_model" name="tk_article_ai_model" value="<?php echo esc_attr( get_option( 'tk_article_ai_model', 'gpt-4o-mini' ) ); ?>" class="regular-text" />
							<p class="description"><?php esc_html_e( 'Any OpenAI chat-completions model name, e.g. gpt-4o-mini, gpt-4o.', 'tk-article' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><?php esc_html_e( 'Content Protection', 'tk-article' ); ?></th>
						<td>
							<label>
								<input type="checkbox" name="tk_article_content_protection" value="1" <?php checked( 1, (int) get_option( 'tk_article_content_protection', 0 ) ); ?> />
								<?php esc_html_e( 'Disable right-click and copy on published posts', 'tk-article' ); ?>
							</label>
							<p class="description"><?php esc_html_e( 'Protects your own original writing from casual copy-pasting. Not foolproof, and has no effect on view-source or screen readers.', 'tk-article' ); ?></p>
						</td>
					</tr>
				</table>
				<?php submit_button(); ?>
			</form>
		</div>
		<?php
	}

	public function enqueue_assets( $hook ) {
		if ( ! in_array( $hook, array( 'post.php', 'post-new.php' ), true ) ) {
			return;
		}

		$screen = get_current_screen();
		if ( ! $screen || 'post' !== $screen->post_type ) {
			return;
		}

		wp_enqueue_style( 'tk-article-admin', TK_ARTICLE_URL . 'assets/css/tk-article-admin.css', array(), TK_ARTICLE_VERSION );
		wp_enqueue_script( 'tk-article-admin', TK_ARTICLE_URL . 'assets/js/tk-article-admin.js', array( 'jquery' ), TK_ARTICLE_VERSION, true );

		global $post;
		wp_localize_script(
			'tk-article-admin',
			'tkArticleData',
			array(
				'ajaxUrl'   => admin_url( 'admin-ajax.php' ),
				'nonce'     => wp_create_nonce( 'tk_article_nonce' ),
				'postId'    => $post ? $post->ID : 0,
				'hasApiKey' => (bool) get_option( 'tk_article_api_key', '' ),
				'strings'   => array(
					'loading'        => __( 'Working…', 'tk-article' ),
					'fetchError'     => __( 'Could not load that content. Check the URL and try again.', 'tk-article' ),
					'aiError'        => __( 'AI request failed. Check your API key in Settings → TK Article.', 'tk-article' ),
					'needApiKey'     => __( 'Add an API key in Settings → TK Article to use AI tools.', 'tk-article' ),
					'contentLoaded'  => __( 'Content loaded into the editor. You can now use the AI tools below.', 'tk-article' ),
					'videoGenerated' => __( 'Post drafted from your video. Review before publishing.', 'tk-article' ),
					'captionReady'   => __( 'Facebook caption ready below.', 'tk-article' ),
					'thumbDone'      => __( 'Thumbnail downloaded.', 'tk-article' ),
				),
			)
		);
	}

	public function render_panel( $post ) {
		if ( ! $post || 'post' !== $post->post_type ) {
			return;
		}
		if ( ! current_user_can( 'edit_post', $post->ID ) ) {
			return;
		}
		require TK_ARTICLE_PATH . 'includes/views/panel.php';
	}
}
