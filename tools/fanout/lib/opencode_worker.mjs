#!/usr/bin/env node

import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    sdk: { type: "string" },
    directory: { type: "string" },
    port: { type: "string" },
    model: { type: "string" },
    agent: { type: "string" },
    "worker-id": { type: "string" },
    prompt: { type: "string" },
  },
  strict: true,
});

for (const name of ["sdk", "directory", "port", "model", "agent", "worker-id", "prompt"]) {
  if (!values[name]) {
    throw new Error(`missing --${name}`);
  }
}

const modelSeparator = values.model.indexOf("/");
if (modelSeparator < 1 || modelSeparator === values.model.length - 1) {
  throw new Error("--model must be provider/model");
}
const providerID = values.model.slice(0, modelSeparator);
const modelID = values.model.slice(modelSeparator + 1);
const workerID = values["worker-id"];
const port = Number(values.port);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("--port must be a valid TCP port");
}

const receiptSchema = {
  type: "object",
  additionalProperties: false,
  required: ["worker_id", "outcome", "summary", "result_json"],
  properties: {
    worker_id: { type: "string", const: workerID },
    outcome: {
      type: "string",
      enum: ["completed", "blocked", "failed"],
    },
    summary: { type: "string", minLength: 1, maxLength: 2000 },
    result_json: {
      type: "string",
      description:
        "A JSON-encoded object containing the task-specific result. Choose fields that suit the assigned work.",
    },
  },
};

const sdk = await import(pathToFileURL(values.sdk).href);
let server;
let client;
let sessionID;

try {
  ({ client, server } = await sdk.createOpencode({
    hostname: "127.0.0.1",
    port,
    timeout: 10_000,
  }));

  const created = await client.session.create({
    directory: values.directory,
    title: `fanout ${workerID}`,
  });
  if (!created.data?.id) {
    throw new Error("OpenCode did not create a session");
  }
  sessionID = created.data.id;

  const response = await client.session.prompt({
    sessionID,
    directory: values.directory,
    agent: values.agent,
    model: { providerID, modelID },
    format: {
      type: "json_schema",
      schema: receiptSchema,
      retryCount: 2,
    },
    parts: [
      {
        type: "text",
        text:
          `${values.prompt.trim()}\n\n` +
          `Fan-out receipt: your assigned worker_id is ${workerID}. ` +
          "Complete the task using the selected agent's normal capabilities. " +
          "Return the task-specific answer as a JSON object encoded in result_json. " +
          "Use outcome=blocked or failed only when appropriate and explain why in summary.",
      },
    ],
  });

  if (!response?.data) {
    throw new Error("OpenCode returned no assistant message");
  }
  if (response.data.info?.error) {
    process.stdout.write(
      `${JSON.stringify({ status: "ERROR", error: response.data.info.error, session_id: sessionID })}\n`,
    );
  } else {
    process.stdout.write(
      `${JSON.stringify({
        status: "SUCCESS",
        structured_output: response.data.info?.structured,
        usage: {
          cost: response.data.info?.cost,
          tokens: response.data.info?.tokens,
        },
        session_id: sessionID,
      })}\n`,
    );
  }
} finally {
  if (client && sessionID) {
    try {
      await client.session.delete({ sessionID, directory: values.directory });
    } catch (error) {
      process.stderr.write(`session cleanup failed: ${error.message}\n`);
    }
  }
  server?.close();
}
