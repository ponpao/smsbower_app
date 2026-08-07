<?php
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Turns a YouTube video the user owns into a draft post: metadata via oEmbed,
 * best-effort transcript, an AI-drafted body, the video embedded, and its
 * thumbnail queued as the featured image.
 */
class TK_Article_Youtube {

	/**
	 * @return array|WP_Error
	 */
	public static function generate( $url ) {
		$video_id = self::extract_id( $url );
		if ( ! $video_id ) {
			return new WP_Error( 'tk_article_yt_id', __( 'That does not look like a YouTube video URL.', 'tk-article' ) );
		}

		$meta = self::oembed( $url );
		if ( is_wp_error( $meta ) ) {
			return $meta;
		}

		$transcript = self::transcript( $video_id );
		$api_key    = get_option( 'tk_article_api_key', '' );
		$body       = '';

		if ( ! empty( $api_key ) && ( $transcript || $meta['title'] ) ) {
			$system = 'You write a blog post based on a YouTube video\'s title, channel and transcript/description. Write in the same language as the source material. Return HTML using only <p>, <h2>, <h3>, <strong>, <em>, <ul>, <li> tags. Do not invent facts not present in the source material.';
			$source = "Video title: {$meta['title']}\nChannel: {$meta['author']}\n\nTranscript or description:\n" . mb_substr( $transcript, 0, 6000 );

			$ai_body = TK_Article_AI::chat( $system, $source, $api_key );
			if ( ! is_wp_error( $ai_body ) ) {
				$body = $ai_body;
			}
		}

		if ( empty( $body ) ) {
			$fallback = $transcript ? wp_trim_words( $transcript, 120 ) : $meta['title'];
			$body     = '<p>' . esc_html( $fallback ) . '</p>';
		}

		$embed_url = 'https://www.youtube.com/watch?v=' . rawurlencode( $video_id );
		$embed     = '<figure class="wp-block-embed is-type-video wp-block-embed-youtube"><div class="wp-block-embed__wrapper">' . esc_url( $embed_url ) . '</div></figure>';
		$content   = $embed . "\n\n" . $body;

		return array(
			'title'     => sanitize_text_field( $meta['title'] ),
			'content'   => wp_kses_post( $content ),
			'thumbnail' => esc_url_raw( "https://img.youtube.com/vi/{$video_id}/maxresdefault.jpg" ),
			'source'    => esc_url_raw( $url ),
		);
	}

	public static function extract_id( $url ) {
		if ( preg_match( '~(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{11})~', $url, $matches ) ) {
			return $matches[1];
		}
		return '';
	}

	/**
	 * @return array|WP_Error
	 */
	private static function oembed( $url ) {
		$response = wp_remote_get(
			add_query_arg(
				array(
					'url'    => rawurlencode( $url ),
					'format' => 'json',
				),
				'https://www.youtube.com/oembed'
			),
			array( 'timeout' => 15 )
		);

		if ( is_wp_error( $response ) ) {
			return $response;
		}

		if ( 200 !== wp_remote_retrieve_response_code( $response ) ) {
			return new WP_Error( 'tk_article_yt_oembed', __( 'Could not read that video\'s details. Is it public?', 'tk-article' ) );
		}

		$data = json_decode( wp_remote_retrieve_body( $response ), true );

		return array(
			'title'  => isset( $data['title'] ) ? $data['title'] : '',
			'author' => isset( $data['author_name'] ) ? $data['author_name'] : '',
		);
	}

	/**
	 * Best-effort auto-caption fetch. Returns '' when unavailable — the
	 * caller falls back to title/description only.
	 */
	private static function transcript( $video_id ) {
		$response = wp_remote_get( "https://video.google.com/timedtext?lang=en&v={$video_id}", array( 'timeout' => 15 ) );
		if ( is_wp_error( $response ) || 200 !== wp_remote_retrieve_response_code( $response ) ) {
			return '';
		}

		$xml = wp_remote_retrieve_body( $response );
		if ( empty( $xml ) ) {
			return '';
		}

		libxml_use_internal_errors( true );
		$doc = simplexml_load_string( $xml );
		libxml_clear_errors();

		if ( ! $doc ) {
			return '';
		}

		$lines = array();
		foreach ( $doc->text as $line ) {
			$lines[] = html_entity_decode( (string) $line, ENT_QUOTES );
		}

		return trim( implode( ' ', $lines ) );
	}
}
