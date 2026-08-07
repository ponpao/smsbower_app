<?php
/**
 * Plugin Name: TK Article
 * Description: AI-assisted writing panel for the Add Post screen — turn your own draft or your own YouTube video into a polished, ready-to-edit post.
 * Version: 1.0.0
 * Author: TK
 * Text Domain: tk-article
 * Requires PHP: 7.4
 * Requires at least: 5.8
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'TK_ARTICLE_VERSION', '1.0.0' );
define( 'TK_ARTICLE_PATH', plugin_dir_path( __FILE__ ) );
define( 'TK_ARTICLE_URL', plugin_dir_url( __FILE__ ) );

require_once TK_ARTICLE_PATH . 'includes/class-tk-article-ai.php';
require_once TK_ARTICLE_PATH . 'includes/class-tk-article-importer.php';
require_once TK_ARTICLE_PATH . 'includes/class-tk-article-youtube.php';
require_once TK_ARTICLE_PATH . 'includes/class-tk-article-ajax.php';
require_once TK_ARTICLE_PATH . 'includes/class-tk-article-admin.php';
require_once TK_ARTICLE_PATH . 'includes/class-tk-article-protection.php';

/**
 * Boots the plugin once all plugins are loaded so class references resolve safely.
 */
function tk_article_init() {
	TK_Article_Admin::instance();
	TK_Article_Ajax::instance();
	TK_Article_Protection::instance();
}
add_action( 'plugins_loaded', 'tk_article_init' );
