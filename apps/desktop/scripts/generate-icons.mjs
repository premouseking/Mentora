import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const desktopDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const buildDir = path.join(desktopDir, "build");
const svgPath = path.join(buildDir, "icon.svg");
const icoSizes = [16, 24, 32, 48, 64, 128, 256];

async function renderPng(svg, size) {
  return sharp(Buffer.from(svg))
    .resize(size, size, { fit: "fill" })
    .png()
    .toBuffer();
}

function createIco(images) {
  const directorySize = 6 + images.length * 16;
  const header = Buffer.alloc(directorySize);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);

  let offset = directorySize;
  images.forEach(({ size, buffer }, index) => {
    const entryOffset = 6 + index * 16;
    header.writeUInt8(size === 256 ? 0 : size, entryOffset);
    header.writeUInt8(size === 256 ? 0 : size, entryOffset + 1);
    header.writeUInt8(0, entryOffset + 2);
    header.writeUInt8(0, entryOffset + 3);
    header.writeUInt16LE(1, entryOffset + 4);
    header.writeUInt16LE(32, entryOffset + 6);
    header.writeUInt32LE(buffer.length, entryOffset + 8);
    header.writeUInt32LE(offset, entryOffset + 12);
    offset += buffer.length;
  });

  return Buffer.concat([header, ...images.map(({ buffer }) => buffer)]);
}

await fs.mkdir(buildDir, { recursive: true });
const svg = await fs.readFile(svgPath, "utf8");
const masterPng = await renderPng(svg, 1024);
const developmentPng = await renderPng(svg, 256);
const icoImages = [];

for (const size of icoSizes) {
  icoImages.push({
    size,
    buffer: await renderPng(svg, size),
  });
}

await Promise.all([
  fs.writeFile(path.join(buildDir, "icon.png"), masterPng),
  fs.writeFile(path.join(buildDir, "icon-dev.png"), developmentPng),
  fs.writeFile(path.join(buildDir, "icon.ico"), createIco(icoImages)),
]);

console.log(`Generated Mentora icons in ${buildDir}`);
