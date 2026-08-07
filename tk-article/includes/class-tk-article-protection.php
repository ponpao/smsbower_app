<?php
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Optional front-end protection for the user's own published posts:
 * blocks right-click, selection and copy. Deliberately does not attempt
 * any devtools detection/blocking — that class of trick punishes legitimate
 * readers (and screen readers) far more than it deters anyone determined.
 */
class TK_Article_Protection {

	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'wp_footer', array( $this, 'output' ) );
	}

	public function output() {
		if ( ! is_singular( 'post' ) ) {
			return;
		}
		if ( ! (int) get_option( 'tk_article_content_protection', 0 ) ) {
			return;
		}
		?>
		<style>
			body.single-post :not(input):not(textarea) { -webkit-user-select: none; user-select: none; }
		</style>
		<script>
		(function () {
			document.addEventListener( 'contextmenu', function ( e ) { e.preventDefault(); } );
			document.addEventListener( 'copy', function ( e ) { e.preventDefault(); } );
		})();
		</script>
		<?php
	}
}
