// node tests/js_parity.mjs -> the JS port must agree with the Python model on every fixture pair.
import { readFileSync } from "node:fs";
import { reduce } from "../js/request-status.mjs";
const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url)));
const contract = read("../request_status_ui/events_v1.json");
let bad = 0;
for (const name of ["req-intake-07", "dedicated-worker"]) {
  const got = JSON.stringify(reduce(read(`../fixtures/${name}.events.json`), contract.plain_copy, "you"));
  const want = JSON.stringify(read(`../fixtures/${name}.expected.json`));
  if (got !== want) { bad++; console.error(`${name}: JS port differs from the Python model`); console.error(got); console.error(want); }
}
if (bad) process.exit(1);
console.log("JS parity ok (2 fixtures)");
