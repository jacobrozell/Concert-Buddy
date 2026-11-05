// cb-shazam: asks Shazam which song is playing in each concert clip.
//
//   cb-shazam [--window 10] [--max-windows 4] [--pause 0.3] FILE...
//
// For every file it listens to a few short windows spread across the clip (Shazam
// identifies from 3–12 seconds of audio; it listens to 10) and prints one JSON line:
//   {"file": "...", "seconds": 84.2, "windows": [{"at": 0, "title": "...", "artist": "...", "shazamID": "..."}, ...]}
// A window Shazam doesn't recognise has no title; a failure has "error".
// It stops early once two windows agree. Built and signed by build.sh; run by
// scripts/shazam_tag.py. Needs macOS 14+.
import AVFoundation
import Foundation
import ShazamKit

struct Window: Encodable {
    var at: Double
    var title: String?
    var artist: String?
    var shazamID: String?
    var isrc: String?
    var appleMusicURL: String?
    var error: String?
    var level: Double?      // loudness of the audio sent to Shazam, dBFS (-100 = silence)
    var heard: Double?      // seconds of audio in the signature
}

struct Clip: Encodable {
    var file: String
    var seconds: Double = 0
    var track: String?      // codec of the audio track listened to, e.g. "aac "
    var windows: [Window] = []
    var error: String?
}

enum ListenError: Error, CustomStringConvertible {
    case noAudio
    case unreadable(String)
    var description: String {
        switch self {
        case .noAudio: return "no audio track"
        case .unreadable(let why): return "couldn't read the audio (\(why))"
        }
    }
}

// ---------- arguments ----------
var windowLength = 10.0   // Shazam's catalog takes 3–12 s; decoding can overshoot by a few samples, so stay under
var maxWindows = 4
var pause = 0.3
var useAsset = false      // --asset: let ShazamKit read the audio itself instead of our decoder
var dumpDir: String?      // --dump DIR: also save each window's audio as a .wav, to listen to
var files: [String] = []
var argv = Array(CommandLine.arguments.dropFirst())
while !argv.isEmpty {
    let a = argv.removeFirst()
    switch a {
    case "--window": windowLength = min(11.5, max(3.5, Double(argv.removeFirst()) ?? windowLength))
    case "--max-windows": maxWindows = Int(argv.removeFirst()) ?? maxWindows
    case "--pause": pause = Double(argv.removeFirst()) ?? pause
    case "--asset": useAsset = true
    case "--dump": dumpDir = argv.removeFirst()
    case "-h", "--help":
        print("usage: cb-shazam [--window SECONDS] [--max-windows N] [--pause SECONDS] [--asset] [--dump DIR] FILE...")
        exit(0)
    default: files.append(a)
    }
}
if files.isEmpty {
    FileHandle.standardError.write("cb-shazam: give it one or more video or audio files\n".data(using: .utf8)!)
    exit(2)
}

// ---------- audio → Shazam signature ----------
let pcm = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: 44100, channels: 1, interleaved: false)!
let pcmSettings: [String: Any] = [
    AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 44100, AVNumberOfChannelsKey: 1,
    AVLinearPCMBitDepthKey: 32, AVLinearPCMIsFloatKey: true, AVLinearPCMIsBigEndianKey: false,
    AVLinearPCMIsNonInterleaved: false,
]

/// A Shazam signature of `length` seconds of the clip's audio starting at `start`,
/// and how loud that audio was (dBFS), so a decoding problem (silence) shows up.
@MainActor func signature(_ asset: AVURLAsset, track: AVAssetTrack, start: Double, length: Double, dump: URL?) throws -> (SHSignature, Double) {
    let reader = try AVAssetReader(asset: asset)
    reader.timeRange = CMTimeRange(start: CMTime(seconds: start, preferredTimescale: 600),
                                   duration: CMTime(seconds: length, preferredTimescale: 600))
    let output = AVAssetReaderTrackOutput(track: track, outputSettings: pcmSettings)
    output.alwaysCopiesSampleData = false
    reader.add(output)
    guard reader.startReading() else { throw ListenError.unreadable(reader.error?.localizedDescription ?? "start") }
    let generator = SHSignatureGenerator()
    let file = try dump.map { try AVAudioFile(forWriting: $0, settings: pcm.settings) }
    var sumSquares = 0.0, count = 0, failed = 0
    while let sample = output.copyNextSampleBuffer() {
        let frames = AVAudioFrameCount(CMSampleBufferGetNumSamples(sample))
        guard frames > 0, let buffer = AVAudioPCMBuffer(pcmFormat: pcm, frameCapacity: frames) else { continue }
        buffer.frameLength = frames
        let status = CMSampleBufferCopyPCMDataIntoAudioBufferList(sample, at: 0, frameCount: Int32(frames), into: buffer.mutableAudioBufferList)
        guard status == noErr else { failed += 1; continue }
        if let ch = buffer.floatChannelData?[0] {
            for i in 0..<Int(frames) { sumSquares += Double(ch[i] * ch[i]) }
            count += Int(frames)
        }
        try generator.append(buffer, at: nil)
        try file?.write(from: buffer)
    }
    if reader.status == .failed { throw ListenError.unreadable(reader.error?.localizedDescription ?? "read") }
    if count == 0 { throw ListenError.unreadable("no samples decoded (\(failed) buffers failed to copy)") }
    let rms = (sumSquares / Double(count)).squareRoot()
    return (generator.signature(), rms > 0 ? (20 * log10(rms) * 10).rounded() / 10 : -100)
}

/// The same, but ShazamKit reads the audio itself (a cross-check on our decoding).
@MainActor func assetSignature(track: AVAssetTrack, start: Double, length: Double) async throws -> SHSignature {
    let comp = AVMutableComposition()
    guard let t = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) else {
        throw ListenError.unreadable("couldn't make a composition")
    }
    try t.insertTimeRange(CMTimeRange(start: CMTime(seconds: start, preferredTimescale: 600),
                                      duration: CMTime(seconds: length, preferredTimescale: 600)), of: track, at: .zero)
    return try await SHSignatureGenerator.signature(from: comp)
}

/// Four-character codec of an audio track ("aac ", "lpcm", "apac" for iPhone spatial audio…).
func codec(_ track: AVAssetTrack) async -> String {
    guard let desc = (try? await track.load(.formatDescriptions))?.first else { return "?" }
    let c = CMFormatDescriptionGetMediaSubType(desc)
    let bytes = [UInt8((c >> 24) & 255), UInt8((c >> 16) & 255), UInt8((c >> 8) & 255), UInt8(c & 255)]
    return String(bytes: bytes, encoding: .ascii) ?? "?"
}

/// Where to listen: one window for a short clip, otherwise up to `maxWindows` spread evenly.
@MainActor func starts(duration: Double) -> [Double] {
    if duration <= windowLength + 1 { return [0] }
    let count = min(maxWindows, max(1, Int(duration / windowLength)))
    if count == 1 { return [(duration - windowLength) / 2] }
    return (0..<count).map { Double($0) * (duration - windowLength) / Double(count - 1) }
}

// ---------- main loop ----------
let session = SHSession()
let encoder = JSONEncoder()
var warnedAboutAccess = false

for path in files {
    var clip = Clip(file: path)
    do {
        let asset = AVURLAsset(url: URL(fileURLWithPath: path))
        clip.seconds = try await asset.load(.duration).seconds
        let tracks = try await asset.loadTracks(withMediaType: .audio)
        // iPhones that record spatial audio add an "apac" track; listen to the ordinary stereo one
        var picked: (AVAssetTrack, String)?
        for t in tracks {
            let c = await codec(t)
            if picked == nil || (picked!.1 == "apac" && c != "apac") { picked = (t, c) }
        }
        guard let chosen = picked else { throw ListenError.noAudio }
        let track = chosen.0
        clip.track = chosen.1
        if clip.seconds < 3.2 { throw ListenError.unreadable("under 3 seconds") }
        var agree: [String: Int] = [:]
        for at in starts(duration: clip.seconds) {
            var w = Window(at: (at * 10).rounded() / 10)
            do {
                let length = min(windowLength, clip.seconds - at - 0.05)
                let sig: SHSignature
                if useAsset {
                    sig = try await assetSignature(track: track, start: at, length: length)
                } else {
                    let dump = dumpDir.map { URL(fileURLWithPath: $0).appendingPathComponent(
                        "\(URL(fileURLWithPath: path).deletingPathExtension().lastPathComponent)-\(Int(at))s.wav") }
                    let (s, level) = try signature(asset, track: track, start: at, length: length, dump: dump)
                    sig = s
                    w.level = level
                }
                w.heard = (sig.duration * 10).rounded() / 10
                switch await session.result(from: sig) {
                case .match(let match):
                    if let item = match.mediaItems.first {
                        w.title = item.title
                        w.artist = item.artist
                        w.shazamID = item.shazamID
                        w.isrc = item.isrc
                        w.appleMusicURL = item.appleMusicURL?.absoluteString
                    }
                case .noMatch:
                    break
                case .error(let error, _):
                    w.error = String(describing: error)
                    if !warnedAboutAccess {
                        warnedAboutAccess = true
                        FileHandle.standardError.write("""
                            cb-shazam: Shazam returned an error: \(error)
                              If it mentions authorization or a developer token, ShazamKit isn't enabled for this
                              tool's bundle ID yet. See docs/shazam.md in ConcertBuddy.\n
                            """.data(using: .utf8)!)
                    }
                }
            } catch {
                w.error = String(describing: error)
            }
            clip.windows.append(w)
            if let id = w.shazamID ?? w.title {
                agree[id, default: 0] += 1
                if agree[id]! >= 2 { break }  // two windows agree: that's the song
            }
            if pause > 0 { try? await Task.sleep(nanoseconds: UInt64(pause * 1_000_000_000)) }
        }
    } catch {
        clip.error = String(describing: error)
    }
    if var line = try? encoder.encode(clip) {
        line.append(0x0A)
        FileHandle.standardOutput.write(line)
    }
}
