<?php
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Best-effort extraction of title/content/image from a page URL the user
 * provides — meant for importing the user's own previously-published pages.
 */
class TK_Article_Importer {

	/**
	 * @return array|WP_Error
	 */
	public static function fetch_url( $url ) {
		$response = wp_remote_get(
			$url,
			array(
				'timeout'    => 20,
				'user-agent' => 'TK Article/' . TK_ARTICLE_VERSION . '; ' . home_url( '/' ),
			)
		);

		if ( is_wp_error( $response ) ) {
			return $response;
		}

		$code = wp_remote_retrieve_response_code( $response );
		if ( $code < 200 || $code >= 300 ) {
			return new WP_Error( 'tk_article_fetch_http', sprintf( /* translators: %d: HTTP status code */ __( 'The page responded with HTTP %d.', 'tk-article' ), $code ) );
		}

		$html = wp_remote_retrieve_body( $response );
		if ( empty( $html ) ) {
			return new WP_Error( 'tk_article_fetch_empty', __( 'That page had no content to read.', 'tk-article' ) );
		}

		return self::extract( $html, $url );
	}

	/**
	 * @return array|WP_Error
	 */
	private static function extract( $html, $url ) {
		$title = '';
		$image = '';
		$body  = '';

		libxml_use_internal_errors( true );
		$doc = new DOMDocument();
		$doc->loadHTML( '<?xml encoding="utf-8" ?>' . $html );
		libxml_clear_errors();

		$xpath = new DOMXPath( $doc );

		$og_title = $xpath->query( '//meta[@property="og:title"]/@content' );
		if ( $og_title->length ) {
			$title = trim( $og_title->item( 0 )->nodeValue );
		} elseif ( $doc->getElementsByTagName( 'title' )->length ) {
			$title = trim( $doc->getElementsByTagName( 'title' )->item( 0 )->textContent );
		}

		$og_image = $xpath->query( '//meta[@property="og:image"]/@content' );
		if ( $og_image->length ) {
			$image = trim( $og_image->item( 0 )->nodeValue );
		}

		$article_node = $xpath->query( '//article' )->item( 0 );
		if ( ! $article_node ) {
			$best_node  = null;
			$best_score = 0;
			foreach ( $xpath->query( '//div | //main | //section' ) as $node ) {
				$paragraphs = $node->getElementsByTagName( 'p' )->length;
				if ( $paragraphs > $best_score ) {
					$best_score = $paragraphs;
					$best_node  = $node;
				}
			}
			$article_node = $best_node;
		}

		if ( $article_node ) {
			$inner = '';
			foreach ( $article_node->childNodes as $child ) {
				$inner .= $doc->saveHTML( $child );
			}
			$body = wp_kses_post( $inner );
		}

		if ( empty( $title ) ) {
			return new WP_Error( 'tk_article_fetch_notitle', __( 'Could not find a title on that page.', 'tk-article' ) );
		}

		return array(
			'title'   => sanitize_text_field( $title ),
			'content' => $body,
			'image'   => $image ? esc_url_raw( $image ) : '',
			'source'  => esc_url_raw( $url ),
		);
	}
}
