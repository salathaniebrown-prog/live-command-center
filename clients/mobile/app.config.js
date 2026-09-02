const isPreview = process.env.APP_VARIANT === "preview";

module.exports = ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    package: isPreview
      ? "com.salathanielbrown.eagleeyes.preview"
      : "com.salathanielbrown.eagleeyes",
  },
});
