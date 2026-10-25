package dev.skippy.channel;

import android.media.MediaCodec;
import android.media.MediaFormat;
import android.util.Log;
import android.view.Surface;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;

// Câmera ao vivo com latência mínima: lê o MPEG-TS do go2rtc, separa o H.264 (demux de TS mínimo:
// PAT -> PMT -> PID de vídeo -> PES) e entrega cada quadro direto ao decodificador de hardware.
// O MediaPlayer faz o mesmo com ~7 s de buffer fixo; aqui o quadro vai pra tela assim que chega.
public class LiveCam {
    public interface Listener { void onFirstFrame(); void onFailed(String why); }

    final String url;
    final Surface surface;
    final Listener listener;
    volatile boolean running;
    Thread reader, drainer;
    MediaCodec codec;
    HttpURLConnection conn;

    public LiveCam(String url, Surface surface, Listener l) { this.url = url; this.surface = surface; this.listener = l; }

    public void start() {
        running = true;
        reader = new Thread(this::readLoop, "livecam-read");
        reader.start();
    }

    public void stop() {
        running = false;
        try { if (conn != null) conn.disconnect(); } catch (Exception ignored) { }
        try { if (reader != null) reader.interrupt(); } catch (Exception ignored) { }
        try { if (drainer != null) drainer.join(500); } catch (Exception ignored) { }
        synchronized (this) {
            if (codec != null) { try { codec.stop(); } catch (Exception ignored) { } try { codec.release(); } catch (Exception ignored) { } codec = null; }
        }
    }

    void readLoop() {
        String why = "fim do stream";
        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setConnectTimeout(5000); conn.setReadTimeout(8000);
            InputStream in = conn.getInputStream();
            byte[] pkt = new byte[188];
            int pmtPid = -1, vidPid = -1;
            ByteArrayOutputStream pes = new ByteArrayOutputStream(256 * 1024);
            boolean haveSps = false;
            while (running) {
                if (!readFully(in, pkt)) break;
                if (pkt[0] != 0x47) { if (!resync(in, pkt)) break; }
                boolean pusi = (pkt[1] & 0x40) != 0;
                int pid = ((pkt[1] & 0x1F) << 8) | (pkt[2] & 0xFF);
                int afc = (pkt[3] >> 4) & 0x3;
                int off = 4;
                if (afc == 2 || afc == 3) off += 1 + (pkt[4] & 0xFF);
                if (afc == 2 || off >= 188) continue;
                if (pid == 0 && pusi) {                       // PAT
                    int p = off + 1 + (pkt[off] & 0xFF);
                    pmtPid = ((pkt[p + 10] & 0x1F) << 8) | (pkt[p + 11] & 0xFF);
                } else if (pid == pmtPid && pusi && vidPid < 0) { // PMT
                    int p = off + 1 + (pkt[off] & 0xFF);
                    int secLen = ((pkt[p + 1] & 0x0F) << 8) | (pkt[p + 2] & 0xFF);
                    int progInfo = ((pkt[p + 10] & 0x0F) << 8) | (pkt[p + 11] & 0xFF);
                    int q = p + 12 + progInfo, end = Math.min(188 - 4, p + 3 + secLen - 4);
                    while (q + 5 <= end) {
                        int type = pkt[q] & 0xFF;
                        int epid = ((pkt[q + 1] & 0x1F) << 8) | (pkt[q + 2] & 0xFF);
                        int esInfo = ((pkt[q + 3] & 0x0F) << 8) | (pkt[q + 4] & 0xFF);
                        if (type == 0x1B) { vidPid = epid; break; }
                        q += 5 + esInfo;
                    }
                } else if (pid == vidPid) {
                    if (pusi) {
                        if (pes.size() > 0) haveSps = feed(pes.toByteArray(), haveSps);
                        pes.reset();
                        int hdr = 9 + (pkt[off + 8] & 0xFF);       // cabeçalho PES
                        if (off + hdr < 188) pes.write(pkt, off + hdr, 188 - off - hdr);
                    } else {
                        pes.write(pkt, off, 188 - off);
                    }
                }
            }
        } catch (Exception e) {
            why = e.getClass().getSimpleName() + ": " + e.getMessage();
        }
        if (running) { running = false; listener.onFailed(why); }
    }

    // devolve se já houve SPS (só começa a alimentar o decodificador a partir do 1º SPS/quadro-chave)
    boolean feed(byte[] au, boolean haveSps) throws Exception {
        if (!haveSps) {
            if (!hasNal(au, 7)) return false;
            synchronized (this) {
                MediaFormat f = MediaFormat.createVideoFormat("video/avc", 1920, 1080);
                f.setInteger("low-latency", 1);
                codec = MediaCodec.createDecoderByType("video/avc");
                codec.configure(f, surface, null, 0);
                codec.start();
            }
            drainer = new Thread(this::drainLoop, "livecam-drain");
            drainer.start();
        }
        MediaCodec c = codec;
        if (c == null) return true;
        int idx = c.dequeueInputBuffer(200000);
        if (idx >= 0) {
            ByteBuffer b = c.getInputBuffer(idx);
            b.clear();
            int n = Math.min(au.length, b.remaining());
            b.put(au, 0, n);
            c.queueInputBuffer(idx, 0, n, System.nanoTime() / 1000, 0);
        }
        return true;
    }

    void drainLoop() {
        MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
        boolean first = true;
        while (running) {
            MediaCodec c = codec;
            if (c == null) break;
            try {
                int idx = c.dequeueOutputBuffer(info, 100000);
                if (idx >= 0) {
                    c.releaseOutputBuffer(idx, true);        // renderiza já: nada de fila
                    if (first) { first = false; listener.onFirstFrame(); }
                }
            } catch (Exception e) {
                if (running) Log.w("SkippyPonte", "drain", e);
                break;
            }
        }
    }

    static boolean hasNal(byte[] a, int type) {
        for (int i = 0; i + 3 < a.length; i++)
            if (a[i] == 0 && a[i + 1] == 0 && a[i + 2] == 1 && (a[i + 3] & 0x1F) == type) return true;
        return false;
    }

    static boolean readFully(InputStream in, byte[] b) throws Exception {
        int got = 0;
        while (got < b.length) { int r = in.read(b, got, b.length - got); if (r < 0) return false; got += r; }
        return true;
    }

    static boolean resync(InputStream in, byte[] pkt) throws Exception {
        for (int i = 0; i < 188 * 4; i++) {
            int c = in.read(); if (c < 0) return false;
            if (c == 0x47) { pkt[0] = 0x47; byte[] rest = new byte[187]; if (!readFully(in, rest)) return false;
                System.arraycopy(rest, 0, pkt, 1, 187); return true; }
        }
        return false;
    }
}
