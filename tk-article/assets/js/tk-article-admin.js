(function ($) {
	'use strict';

	var state = {
		thumbnailUrl: ''
	};

	function showStatus(message, type) {
		var $status = $('#tk-article-status');
		$status.removeClass('is-success is-error is-info').addClass('is-' + (type || 'info'));
		$status.text(message).prop('hidden', false);
	}

	function setBusy($btn, busy) {
		$btn.prop('disabled', busy).toggleClass('is-busy', busy);
	}

	function setTitle(title) {
		var $title = $('#title');
		if ($title.length) {
			$title.val(title).trigger('input').trigger('change');
		}
	}

	function getTitle() {
		return $('#title').val() || '';
	}

	function setContent(html) {
		if (typeof tinymce !== 'undefined' && tinymce.get('content') && !tinymce.get('content').isHidden()) {
			tinymce.get('content').setContent(html);
		}
		var $content = $('#content');
		if ($content.length) {
			$content.val(html);
		}
	}

	function getContent() {
		if (typeof tinymce !== 'undefined' && tinymce.get('content') && !tinymce.get('content').isHidden()) {
			return tinymce.get('content').getContent();
		}
		return $('#content').val() || '';
	}

	function enableToolbar() {
		$('.tk-article-toolbar .tk-article-btn').prop('disabled', false);
	}

	function sideloadThumbnail(imageUrl) {
		if (!imageUrl || !tkArticleData.postId) {
			return;
		}
		state.thumbnailUrl = imageUrl;
		$.post(tkArticleData.ajaxUrl, {
			action: 'tk_article_sideload_image',
			nonce: tkArticleData.nonce,
			post_id: tkArticleData.postId,
			image_url: imageUrl
		}).done(function (res) {
			if (res.success && window.wp && wp.media && wp.media.featuredImage) {
				wp.media.featuredImage.set(res.data.attachmentId);
			}
		});
	}

	function loadImported(data) {
		setTitle(data.title || '');
		setContent(data.content || '');
		enableToolbar();
		if (data.image || data.thumbnail) {
			sideloadThumbnail(data.image || data.thumbnail);
		}
	}

	function runAiAction(actionType, $btn, onSuccess) {
		if (!tkArticleData.hasApiKey) {
			showStatus(tkArticleData.strings.needApiKey, 'error');
			return;
		}
		setBusy($btn, true);
		showStatus(tkArticleData.strings.loading, 'info');

		$.post(tkArticleData.ajaxUrl, {
			action: 'tk_article_ai_action',
			nonce: tkArticleData.nonce,
			action_type: actionType,
			title: getTitle(),
			content: getContent()
		}).done(function (res) {
			if (res.success) {
				onSuccess(res.data);
			} else {
				showStatus(res.data && res.data.message ? res.data.message : tkArticleData.strings.aiError, 'error');
			}
		}).fail(function () {
			showStatus(tkArticleData.strings.aiError, 'error');
		}).always(function () {
			setBusy($btn, false);
		});
	}

	$(function () {
		$('.tk-article-tab').on('click', function () {
			var tab = $(this).data('tab');
			$('.tk-article-tab').removeClass('is-active');
			$(this).addClass('is-active');
			$('.tk-article-tabpanel').removeClass('is-active');
			$('.tk-article-tabpanel[data-panel="' + tab + '"]').addClass('is-active');
		});

		$('.tk-article-subtab').on('click', function () {
			var mode = $(this).data('mode');
			$('.tk-article-subtab').removeClass('is-active');
			$(this).addClass('is-active');
			$('.tk-article-mode').removeClass('is-active');
			$('.tk-article-mode[data-mode-panel="' + mode + '"]').addClass('is-active');
		});

		$('#tk-article-load-paste').on('click', function () {
			var title = $('#tk-article-paste-title').val();
			var body = $('#tk-article-paste-body').val();
			var image = $('#tk-article-paste-image').val();

			if (!title && !body) {
				showStatus(tkArticleData.strings.fetchError, 'error');
				return;
			}

			var html = body.indexOf('<') === -1
				? '<p>' + body.split(/\n{2,}/).join('</p><p>') + '</p>'
				: body;

			loadImported({ title: title, content: html, image: image });
			showStatus(tkArticleData.strings.contentLoaded, 'success');
		});

		$('#tk-article-fetch-url').on('click', function () {
			var $btn = $(this);
			var url = $('#tk-article-url').val();
			if (!url) {
				return;
			}
			setBusy($btn, true);
			showStatus(tkArticleData.strings.loading, 'info');

			$.post(tkArticleData.ajaxUrl, {
				action: 'tk_article_fetch_url',
				nonce: tkArticleData.nonce,
				url: url
			}).done(function (res) {
				if (res.success) {
					loadImported(res.data);
					showStatus(tkArticleData.strings.contentLoaded, 'success');
				} else {
					showStatus(res.data && res.data.message ? res.data.message : tkArticleData.strings.fetchError, 'error');
				}
			}).fail(function () {
				showStatus(tkArticleData.strings.fetchError, 'error');
			}).always(function () {
				setBusy($btn, false);
			});
		});

		$('#tk-article-generate-yt').on('click', function () {
			var $btn = $(this);
			var url = $('#tk-article-yt-url').val();
			if (!url) {
				return;
			}
			setBusy($btn, true);
			showStatus(tkArticleData.strings.loading, 'info');

			$.post(tkArticleData.ajaxUrl, {
				action: 'tk_article_youtube_generate',
				nonce: tkArticleData.nonce,
				url: url
			}).done(function (res) {
				if (res.success) {
					loadImported(res.data);
					showStatus(tkArticleData.strings.videoGenerated, 'success');
				} else {
					showStatus(res.data && res.data.message ? res.data.message : tkArticleData.strings.fetchError, 'error');
				}
			}).fail(function () {
				showStatus(tkArticleData.strings.fetchError, 'error');
			}).always(function () {
				setBusy($btn, false);
			});
		});

		$('#tk-article-rewrite-title').on('click', function () {
			runAiAction('rewrite_title', $(this), function (data) {
				setTitle(data.title);
				showStatus(tkArticleData.strings.contentLoaded, 'success');
			});
		});

		$('#tk-article-improve-content').on('click', function () {
			runAiAction('improve_content', $(this), function (data) {
				setContent(data.content);
				showStatus(tkArticleData.strings.contentLoaded, 'success');
			});
		});

		$('#tk-article-reformat-content').on('click', function () {
			runAiAction('reformat_content', $(this), function (data) {
				setContent(data.content);
				showStatus(tkArticleData.strings.contentLoaded, 'success');
			});
		});

		$('#tk-article-fb-caption').on('click', function () {
			runAiAction('fb_caption', $(this), function (data) {
				$('#tk-article-caption-output').prop('hidden', false);
				$('#tk-article-caption-text').val(data.caption);
				showStatus(tkArticleData.strings.captionReady, 'success');
			});
		});

		$('#tk-article-download-thumb').on('click', function () {
			if (!state.thumbnailUrl) {
				return;
			}
			fetch(state.thumbnailUrl).then(function (r) {
				return r.blob();
			}).then(function (blob) {
				var link = document.createElement('a');
				link.href = URL.createObjectURL(blob);
				link.download = 'tk-article-thumbnail.jpg';
				document.body.appendChild(link);
				link.click();
				link.remove();
				showStatus(tkArticleData.strings.thumbDone, 'success');
			}).catch(function () {
				window.open(state.thumbnailUrl, '_blank');
			});
		});
	});
})(jQuery);
