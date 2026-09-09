'use strict';
const REPOSITORY = 'salathaniebrown-prog/live-command-center';
async function run() {
  const token = process.env.RAILWAY_PROJECT_TOKEN;
  const expected = process.env.EXPECTED_SHA;
  if (!token) throw new Error('Configure the production environment secret RAILWAY_PROJECT_TOKEN, scoped to the existing Railway production environment.');
  if (!/^[a-f0-9]{40}$/.test(expected || '')) throw new Error('Invalid expected SHA');
  const head = await fetch(`https://api.github.com/repos/${REPOSITORY}/git/ref/heads/main`, {
    headers: { Authorization: `Bearer ${process.env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json' },
    signal: AbortSignal.timeout(10000), redirect: 'error'
  });
  if (!head.ok || (await head.json()).object?.sha !== expected) throw new Error('Main changed since validation. Run checks for the new revision.');
  const response = await fetch('https://backboard.railway.com/graphql/v2', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Project-Access-Token': token },
    body: JSON.stringify({
      query: 'mutation serviceInstanceDeployV2($serviceId: String!, $environmentId: String!, $commitSha: String!) { serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId, commitSha: $commitSha) }',
      variables: { serviceId: '6d5434d1-7e63-4cc1-ace6-6967e9dc4b01', environmentId: 'e734218b-4942-4e20-ad50-33e860cf226c', commitSha: expected }
    }), signal: AbortSignal.timeout(20000), redirect: 'error'
  });
  if (!response.ok) throw new Error(`Railway request returned HTTP ${response.status}; inspect deployment history before retrying.`);
  const data = await response.json();
  if (data.errors?.length || !data.data?.serviceInstanceDeployV2) throw new Error('Railway rejected the deployment request; inspect the production service configuration.');
  console.log(JSON.stringify({ requested: true, deploymentId: data.data.serviceInstanceDeployV2, expectedCommit: expected }));
}
run().catch(error => { console.error(error.message); process.exitCode = 1; });
