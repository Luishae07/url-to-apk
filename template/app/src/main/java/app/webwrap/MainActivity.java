package app.webwrap;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.GeolocationPermissions;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/** Shows one website full screen. Links to other websites open in the normal browser. */
public class MainActivity extends Activity {
    static final String START_URL = "__URL__";
    static final boolean LOCATION = __LOCATION__;
    static final String BAR_COLOR = "__COLOR__";

    private WebView web;
    private GeolocationPermissions.Callback pendingGeo;
    private String pendingGeoOrigin;

    private static String baseHost(String host) {
        if (host == null) return "";
        host = host.toLowerCase();
        return host.startsWith("www.") ? host.substring(4) : host;
    }

    private boolean sameSite(Uri u) {
        String a = baseHost(Uri.parse(START_URL).getHost());
        String b = baseHost(u.getHost());
        return a.equals(b) || b.endsWith("." + a);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try { getWindow().setStatusBarColor(Color.parseColor(BAR_COLOR)); } catch (Exception ignored) { }
        web = new WebView(this);
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setGeolocationEnabled(LOCATION);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setAllowFileAccess(false);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                String scheme = u.getScheme() == null ? "" : u.getScheme();
                if ((scheme.equals("http") || scheme.equals("https")) && sameSite(u)) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    view.loadData("<meta name=viewport content='width=device-width,initial-scale=1'>"
                            + "<body style='font:18px sans-serif;text-align:center;padding:30vh 24px 0;color:#444'>"
                            + "<h2>Can't reach the website</h2><p>Check your connection.</p>"
                            + "<p><a href='" + START_URL + "'>Try again</a></p></body>", "text/html", "UTF-8");
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback callback) {
                if (!LOCATION) { callback.invoke(origin, false, false); return; }
                if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                    callback.invoke(origin, true, false);
                } else {
                    pendingGeo = callback;
                    pendingGeoOrigin = origin;
                    requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION}, 1);
                }
            }
        });

        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else web.loadUrl(START_URL);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        if (pendingGeo != null) {
            boolean ok = results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED;
            pendingGeo.invoke(pendingGeoOrigin, ok, false);
            pendingGeo = null;
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        web.saveState(out);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }
}
