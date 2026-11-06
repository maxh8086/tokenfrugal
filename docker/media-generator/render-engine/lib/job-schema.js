import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';

export const presets = Object.freeze({
  youtube: Object.freeze({ width: 1920, height: 1080, fps: 30 }),
  shorts: Object.freeze({ width: 1080, height: 1920, fps: 30 }),
});

const schemaPath = fileURLToPath(new URL('../schemas/job.schema.json', import.meta.url));

const ajv = new Ajv2020({ allErrors: true, strict: true });
let validatorPromise = null;

function getValidator() {
  if (!validatorPromise) {
    validatorPromise = readFile(schemaPath, 'utf8').then((text) => ajv.compile(JSON.parse(text)));
  }
  return validatorPromise;
}

export async function validateJob(job) {
  const validate = await getValidator();
  const valid = validate(job);
  const errors = valid
    ? []
    : validate.errors.map((e) => `${e.instancePath || '/'} ${e.message}`);
  return { valid: Boolean(valid), errors };
}
