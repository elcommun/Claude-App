/**
 * laikle-convert 変換完了メール送信用のGoogle Apps Script。
 *
 * デプロイ手順は同じフォルダの README.md を参照。
 * ウェブアプリとしてデプロイし、発行されたURLを laikle-convert/index.html の
 * MAIL_WEBHOOK_URL に設定すると、変換完了時に自動でメールが届く。
 */

// 送信先。変更する場合はここを書き換えて再デプロイする
const MAIL_TO = 'ec@elcommun.co.jp';

// index.html の MAIL_TOKEN と同じ文字列にする（第三者からの送信を防ぐための合言葉）
const MAIL_TOKEN = 'laikle-convert-mail-2026';

function doPost(e) {
  try {
    const data = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    if (data.token !== MAIL_TOKEN) return json({ ok: false, error: 'invalid token' });

    MailApp.sendEmail({
      to: MAIL_TO,
      subject: String(data.subject || '【laikle-convert】変換が完了しました').slice(0, 200),
      body: String(data.body || '').slice(0, 20000),
    });
    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

// 動作確認用（ブラウザでウェブアプリURLを開くとこの応答が返る）
function doGet() {
  return json({ ok: true, message: 'laikle-convert mail webhook is running' });
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
