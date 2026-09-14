#!/usr/bin/env node

import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { setTimeout as sleep } from "node:timers/promises";

const { values } = parseArgs({
  options: Object.fromEntries(
    ["sdk", "directory", "port", "model", "agent", "worker-id", "prompt"].map(
      (name) => [name, { type: "string" }],
    ),
  ),
  strict: true,
});
for (const name of ["sdk", "directory", "port", "model", "agent", "worker-id", "prompt"]) {
  if (!values[name]) throw new Error(`missing --${name}`);
}
const separator = values.model.indexOf("/");
if (separator < 1 || separator === values.model.length - 1) {
  throw new Error("--model must be provider/model");
}
const model = {
  providerID: values.model.slice(0, separator),
  modelID: values.model.slice(separator + 1),
};
const port = Number(values.port);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("--port must be a valid TCP port");
}
const options = () => ({ signal: AbortSignal.timeout(10_000) });
function checked(response, operation) {
  if (response.error) throw new Error(`${operation}: ${JSON.stringify(response.error)}`);
  return response.data;
}

const sdk = await import(pathToFileURL(values.sdk).href);
let server;
let client;
let sessionID;
try {
  ({ client, server } = await sdk.createOpencode({
    hostname: "127.0.0.1", port, timeout: 10_000,
    // Preserve injected settings; the SDK otherwise replaces this environment value.
    config: JSON.parse(process.env.OPENCODE_CONFIG_CONTENT || "{}"),
  }));
  const created = checked(await client.session.create({
    directory: values.directory, title: `fanout ${values["worker-id"]}`,
  }, options()), "create session");
  if (!created?.id) throw new Error("OpenCode did not create a session");
  sessionID = created.id;
  checked(await client.session.promptAsync({
    sessionID, directory: values.directory, agent: values.agent, model,
    parts: [{ type: "text", text:
      `${values.prompt.trim()}\n\nFan-out response contract: return only one JSON object ` +
      "without Markdown fences, with exactly worker_id, outcome, summary, result_json. " +
      `Your worker_id is ${values["worker-id"]}. ` +
      "outcome must be completed, blocked, or failed. summary must be a non-empty string " +
      "of at most 2000 characters. result_json must be a JSON-encoded object containing " +
      "the task-specific answer. Use the selected agent's normal tools and permissions; " +
      "report blocked if required tools or permissions are unavailable. " +
      "result_json is a STRING, not a nested object. Use this exact outer shape, " +
      "replacing the example answer:\n" + JSON.stringify({
        worker_id: values["worker-id"], outcome: "completed", summary: "Completed task",
        result_json: JSON.stringify({ answer: "replace with task-specific fields" }),
      }),
    }],
  }, options()), "submit prompt");

  // Async submission avoids the long POST's transport timeout. Polling never
  // resubmits a task; the Python supervisor owns the worker deadline.
  while (true) {
    const statuses = checked(await client.session.status({
      directory: values.directory,
    }, options()), "session status");
    const messages = checked(await client.session.messages({
      sessionID, directory: values.directory,
    }, options()), "session messages");
    if (!statuses || !Array.isArray(messages)) throw new Error("Invalid OpenCode session response");
    const assistant = messages.filter((message) => message.info?.role === "assistant").at(-1);
    const idle = !statuses[sessionID] || statuses[sessionID].type === "idle";
    if (idle && assistant?.info?.time?.completed) {
      if (assistant.info.error) throw new Error(JSON.stringify(assistant.info.error));
      if (assistant.info.finish && assistant.info.finish !== "tool-calls") {
        if (assistant.info.finish !== "stop") {
          throw new Error(`OpenCode did not complete: ${assistant.info.finish}`);
        }
        const text = assistant.parts.filter((part) => part.type === "text")
          .map((part) => part.text).join("");
        const receipt = JSON.parse(text);
        const usage = messages.filter((message) => message.info?.role === "assistant")
          .reduce((total, message) => {
            total.cost += message.info.cost || 0;
            const tokens = message.info.tokens || {};
            total.tokens += tokens.total ?? ((tokens.input || 0) + (tokens.output || 0)
              + (tokens.reasoning || 0) + (tokens.cache?.read || 0) + (tokens.cache?.write || 0));
            return total;
          }, { cost: 0, tokens: 0 });
        process.stdout.write(`${JSON.stringify({
          status: "SUCCESS", structured_output: receipt, usage, session_id: sessionID,
        })}\n`);
        break;
      }
    }
    await sleep(500);
  }
} catch (error) {
  process.stdout.write(`${JSON.stringify({ status: "ERROR", error: String(error), session_id: sessionID })}\n`);
} finally {
  if (client && sessionID) {
    try {
      checked(await client.session.delete({ sessionID, directory: values.directory }, options()), "delete session");
    } catch (error) {
      process.stderr.write(`session cleanup failed: ${error.message}\n`);
    }
  }
  server?.close();
}
