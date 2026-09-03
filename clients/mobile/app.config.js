module.exports = ({ config }) => ({
  ...config,
  name: "Eagle Eyes Recovery",
  android: {
    ...config.android,
    package: "com.salathanielbrown.eagleeyes.recoverytest",
  },
});
