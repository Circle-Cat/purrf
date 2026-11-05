import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

/**
 * Minimal SCORM 1.2 packages for the training specs, a few KB each, laid out
 * like the Rise exports Purrf reads: imsmanifest.xml at the zip root and the
 * entry page at scormdriver/indexAPI.html carrying a __DRIVER_CONFIG__ block.
 *
 * The course is one page with two "pages" inside it. It prints the CMI it was
 * handed (entry, lesson_status, lesson_location, suspend_data length) so a
 * spec can read it off the screen, and its buttons commit page 2 or finish.
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const FIXTURE_DIR = path.join(ROOT, ".state", "scorm");

export const PACKAGES = {
  a: {
    version: "AAAAaaaa",
    finish: "completed",
    reporting: "completed-incomplete",
  },
  b: { version: "BBBBbbbb", finish: "passed", reporting: "passed-incomplete" },
};

const MANIFEST = (version) => `<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="e2e-${version}" version="1.0"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="org">
    <organization identifier="org">
      <title>E2E course ${version}</title>
      <item identifier="item" identifierref="res">
        <title>E2E course ${version}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="res" type="webcontent" adlcp:scormtype="sco" href="scormdriver/indexAPI.html">
      <file href="scormdriver/indexAPI.html"/>
      <file href="scormdriver/course.js"/>
    </resource>
  </resources>
</manifest>
`;

const ENTRY = ({ version, reporting }) => `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>E2E course ${version}</title>
<script id="__DRIVER_CONFIG__" type="application/json">{"reporting":"${reporting}","coursePackageVersion":"${version}","completionPercentage":100}</script>
<style>body{font:16px system-ui;margin:24px}dt{font-weight:600}</style>
</head>
<body>
<h1>E2E course ${version}</h1>
<dl>
<dt>version</dt><dd id="version">${version}</dd>
<dt>entry</dt><dd id="entry">-</dd>
<dt>lesson_status</dt><dd id="status">-</dd>
<dt>lesson_location</dt><dd id="location">-</dd>
<dt>suspend_data length</dt><dd id="suspend">-</dd>
<dt>page</dt><dd id="page">-</dd>
<dt>api</dt><dd id="api">-</dd>
</dl>
<button id="next" type="button">Next page</button>
<button id="finish" type="button">Finish course</button>
<script src="course.js"></script>
</body>
</html>
`;

const COURSE_JS = ({ finish }) => `(function () {
  function findApi(win) {
    for (var i = 0; win && i < 10; i++) {
      if (win.API) return win.API;
      if (win.parent === win) break;
      win = win.parent;
    }
    return null;
  }
  var api = findApi(window);
  var show = function (id, value) { document.getElementById(id).textContent = value; };
  if (!api) { show("api", "missing"); return; }
  show("api", String(api.LMSInitialize("")));
  var get = function (key) { return api.LMSGetValue(key); };
  var render = function () {
    show("entry", get("cmi.core.entry"));
    show("status", get("cmi.core.lesson_status"));
    show("location", get("cmi.core.lesson_location") || "(empty)");
    show("suspend", String((get("cmi.suspend_data") || "").length));
  };
  show("entry", get("cmi.core.entry"));
  show("location", get("cmi.core.lesson_location") || "(empty)");
  show("suspend", String((get("cmi.suspend_data") || "").length));
  show("status", get("cmi.core.lesson_status"));
  show("page", get("cmi.core.lesson_location") === "page-2" ? "2" : "1");
  document.getElementById("next").onclick = function () {
    api.LMSSetValue("cmi.core.lesson_status", "incomplete");
    api.LMSSetValue("cmi.core.lesson_location", "page-2");
    api.LMSSetValue("cmi.suspend_data", "e2e-bookmark:page-2");
    api.LMSCommit("");
    show("page", "2");
    render();
  };
  document.getElementById("finish").onclick = function () {
    api.LMSSetValue("cmi.core.score.raw", "90");
    api.LMSSetValue("cmi.core.lesson_status", "${finish}");
    api.LMSCommit("");
    render();
    api.LMSFinish("");
  };
})();
`;

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/**
 * A deflated zip of `files` ({name: string}). `damage` names a member whose
 * deflate stream is replaced with an invalid block, so the container opens
 * but reading that member fails in zlib.
 */
export function zip(files, { damage } = {}) {
  const locals = [];
  const centrals = [];
  let offset = 0;
  for (const [name, text] of Object.entries(files)) {
    const data = Buffer.from(text);
    let packed = zlib.deflateRawSync(data);
    if (name === damage) packed = Buffer.from([0xff, 0xff, 0xff, 0xff]);
    const nameBuf = Buffer.from(name);
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0, 6);
    local.writeUInt16LE(8, 8);
    local.writeUInt32LE(0, 10);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(packed.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    locals.push(local, nameBuf, packed);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0, 8);
    central.writeUInt16LE(8, 10);
    central.writeUInt32LE(0, 12);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(packed.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt32LE((0o100644 << 16) >>> 0, 38);
    central.writeUInt32LE(offset, 42);
    centrals.push(central, nameBuf);
    offset += local.length + nameBuf.length + packed.length;
  }
  const cd = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(centrals.length / 2, 8);
  end.writeUInt16LE(centrals.length / 2, 10);
  end.writeUInt32LE(cd.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, cd, end]);
}

const packageFiles = (pkg) => ({
  "imsmanifest.xml": MANIFEST(pkg.version),
  "scormdriver/indexAPI.html": ENTRY(pkg),
  "scormdriver/course.js": COURSE_JS(pkg),
});

/** Write every fixture into `dir` and return their paths by name. */
export function writeFixtures(dir = FIXTURE_DIR) {
  fs.mkdirSync(dir, { recursive: true });
  const out = {
    a: path.join(dir, "package-a.zip"),
    b: path.join(dir, "package-b.zip"),
    damaged: path.join(dir, "package-damaged.zip"),
    notZip: path.join(dir, "not-a-package.zip"),
  };
  fs.writeFileSync(out.a, zip(packageFiles(PACKAGES.a)));
  fs.writeFileSync(out.b, zip(packageFiles(PACKAGES.b)));
  fs.writeFileSync(
    out.damaged,
    zip(packageFiles(PACKAGES.a), { damage: "imsmanifest.xml" }),
  );
  fs.writeFileSync(out.notZip, "this is not a zip archive\n");
  return out;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const written = writeFixtures(process.argv[2] ?? FIXTURE_DIR);
  for (const [name, file] of Object.entries(written)) {
    console.log(`${name}\t${file}\t${fs.statSync(file).size} bytes`);
  }
}
