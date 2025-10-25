import { Stagehand } from "@browserbasehq/stagehand";

export async function withStagehand(run) {
  const stagehand = new Stagehand({ env: "BROWSERBASE" });
  await stagehand.init();
  console.log(`Stagehand Session Started`);
  console.log(`Watch live: https://browserbase.com/sessions/${stagehand.browserbaseSessionID}`);
  try {
    return await run(stagehand.page);
  } finally {
    await stagehand.close();
  }
}
