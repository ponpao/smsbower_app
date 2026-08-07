<?php
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * All wp_ajax_* endpoints the admin panel talks to. Every handler verifies
 * the nonce and the edit_posts capability before doing anything.
 */
class TK_Article_Ajax {

	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'wp_ajax_tk_article_fetch_url', array( $this, 'fetch_url' ) );
		add_action( 'wp_ajax_tk_article_youtube_generate', array( $this, 'youtube_generate' ) );
		add_action( 'wp_ajax_tk_article_ai_action', array( $this, 'ai_action' ) );
		add_action( 'wp_ajax_tk_article_sideload_image', array( $this, 'sideload_image' ) );
	}

	private function verify_request() {
		check_ajax_referer( 'tk_article_nonce', 'nonce' );
		if ( ! current_user_can( 'edit_posts' ) ) {
			wp_send_json_error( array( 'message' => __( 'Permission denied.', 'tk-article' ) ), 403 );
		}
	}

	public function fetch_url() {
		$this->verify_request();

		$url = isset( $_POST['url'] ) ? esc_url_raw( wp_unslash( $_POST['url'] ) ) : '';
		if ( empty( $url ) ) {
			wp_send_json_error( array( 'message' => __( 'Please enter a URL.', 'tk-article' ) ) );
		}

		$result = TK_Article_Importer::fetch_url( $url );
		if ( is_wp_error( $result ) ) {
			wp_send_json_error( array( 'message' => $result->get_error_message() ) );
		}

		wp_send_json_success( $result );
	}

	public function youtube_generate() {
		$this->verify_request();

		$url = isset( $_POST['url'] ) ? esc_url_raw( wp_unslash( $_POST['url'] ) ) : '';
		if ( empty( $url ) ) {
			wp_send_json_error( array( 'message' => __( 'Please enter a YouTube URL.', 'tk-article' ) ) );
		}

		$result = TK_Article_Youtube::generate( $url );
		if ( is_wp_error( $result ) ) {
			wp_send_json_error( array( 'message' => $result->get_error_message() ) );
		}

		wp_send_json_success( $result );
	}

	public function ai_action() {
		$this->verify_request();

		$type    = isset( $_POST['action_type'] ) ? sanitize_key( $_POST['action_type'] ) : '';
		$title   = isset( $_POST['title'] ) ? sanitize_text_field( wp_unslash( $_POST['title'] ) ) : '';
		$content = isset( $_POST['content'] ) ? wp_kses_post( wp_unslash( $_POST['content'] ) ) : '';

		$allowed = array( 'rewrite_title', 'improve_content', 'reformat_content', 'fb_caption' );
		if ( ! in_array( $type, $allowed, true ) ) {
			wp_send_json_error( array( 'message' => __( 'Unknown action.', 'tk-article' ) ) );
		}

		$result = TK_Article_AI::run( $type, $title, $content );
		if ( is_wp_error( $result ) ) {
			wp_send_json_error( array( 'message' => $result->get_error_message() ) );
		}

		wp_send_json_success( $result );
	}

	public function sideload_image() {
		$this->verify_request();

		$image_url = isset( $_POST['image_url'] ) ? esc_url_raw( wp_unslash( $_POST['image_url'] ) ) : '';
		$post_id   = isset( $_POST['post_id'] ) ? absint( $_POST['post_id'] ) : 0;

		if ( empty( $image_url ) || ! $post_id || ! current_user_can( 'edit_post', $post_id ) ) {
			wp_send_json_error( array( 'message' => __( 'Cannot save this image.', 'tk-article' ) ) );
		}

		require_once ABSPATH . 'wp-admin/includes/media.php';
		require_once ABSPATH . 'wp-admin/includes/file.php';
		require_once ABSPATH . 'wp-admin/includes/image.php';

		$attachment_id = media_sideload_image( $image_url, $post_id, null, 'id' );
		if ( is_wp_error( $attachment_id ) ) {
			wp_send_json_error( array( 'message' => $attachment_id->get_error_message() ) );
		}

		set_post_thumbnail( $post_id, $attachment_id );

		wp_send_json_success(
			array(
				'attachmentId' => $attachment_id,
				'url'          => wp_get_attachment_url( $attachment_id ),
			)
		);
	}
}
