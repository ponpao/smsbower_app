<?php
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Thin wrapper around an OpenAI-compatible chat-completions endpoint.
 * All prompts operate on content the user already has in their own editor.
 */
class TK_Article_AI {

	public static function run( $type, $title, $content ) {
		$api_key = get_option( 'tk_article_api_key', '' );
		if ( empty( $api_key ) ) {
			return new WP_Error( 'tk_article_no_key', __( 'Add an API key in Settings → TK Article first.', 'tk-article' ) );
		}

		$plain = wp_strip_all_tags( $content );

		switch ( $type ) {
			case 'rewrite_title':
				$system = 'You suggest one improved blog post title for the writer\'s own article. Reply with only the title text, no quotes, same language as the input.';
				$user   = "Current title: {$title}\n\nArticle excerpt:\n" . mb_substr( $plain, 0, 1500 );
				$field  = 'title';
				break;

			case 'improve_content':
				$system = 'You are an editor improving the writer\'s own draft: fix grammar, tighten sentences, keep their voice, meaning and language. Return HTML using only <p>, <h2>, <h3>, <strong>, <em>, <ul>, <li> tags. Do not invent facts that are not already in the draft.';
				$user   = "Title: {$title}\n\nDraft:\n{$content}";
				$field  = 'content';
				break;

			case 'reformat_content':
				$system = 'You clean up HTML structure for readability: add sensible <h2>/<h3> subheadings, break up long paragraphs, keep the original wording intact. Return HTML using only <p>, <h2>, <h3>, <strong>, <em>, <ul>, <li> tags. Do not add or remove factual content.';
				$user   = "Title: {$title}\n\nContent:\n{$content}";
				$field  = 'content';
				break;

			case 'fb_caption':
				$system = 'You write one short, engaging Facebook post caption (2-4 sentences, optionally 1-3 relevant hashtags) promoting the writer\'s own article. Reply with only the caption text, same language as the input.';
				$user   = "Title: {$title}\n\nArticle excerpt:\n" . mb_substr( $plain, 0, 1500 );
				$field  = 'caption';
				break;

			default:
				return new WP_Error( 'tk_article_bad_type', __( 'Unknown AI action.', 'tk-article' ) );
		}

		$text = self::chat( $system, $user, $api_key );
		if ( is_wp_error( $text ) ) {
			return $text;
		}

		return array( $field => $text );
	}

	/**
	 * Sends a single system/user turn to the configured chat-completions model.
	 *
	 * @return string|WP_Error
	 */
	public static function chat( $system, $user, $api_key ) {
		$model = get_option( 'tk_article_ai_model', 'gpt-4o-mini' );

		$response = wp_remote_post(
			'https://api.openai.com/v1/chat/completions',
			array(
				'timeout' => 45,
				'headers' => array(
					'Authorization' => 'Bearer ' . $api_key,
					'Content-Type'  => 'application/json',
				),
				'body'    => wp_json_encode(
					array(
						'model'       => $model,
						'messages'    => array(
							array(
								'role'    => 'system',
								'content' => $system,
							),
							array(
								'role'    => 'user',
								'content' => $user,
							),
						),
						'temperature' => 0.6,
					)
				),
			)
		);

		if ( is_wp_error( $response ) ) {
			return $response;
		}

		$code = wp_remote_retrieve_response_code( $response );
		$body = json_decode( wp_remote_retrieve_body( $response ), true );

		if ( $code < 200 || $code >= 300 ) {
			$message = isset( $body['error']['message'] ) ? $body['error']['message'] : __( 'AI request failed.', 'tk-article' );
			return new WP_Error( 'tk_article_ai_http', $message );
		}

		$text = isset( $body['choices'][0]['message']['content'] ) ? trim( $body['choices'][0]['message']['content'] ) : '';
		if ( '' === $text ) {
			return new WP_Error( 'tk_article_ai_empty', __( 'AI returned an empty response.', 'tk-article' ) );
		}

		return $text;
	}
}
