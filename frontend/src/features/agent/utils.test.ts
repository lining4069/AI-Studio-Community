import { deriveSessionTitle } from "@/features/agent/utils";

describe("deriveSessionTitle", () => {
  it("trims and shortens the first chat message into a session title", () => {
    expect(deriveSessionTitle("   使用网络搜索工具获取最新的华为手机型号   ")).toBe(
      "使用网络搜索工具获取最新的华为手机型号",
    );
    expect(
      deriveSessionTitle(
        "这是一个非常长的消息，用于测试标题在超过限制长度时会自动截断并追加省略号",
        12,
      ),
    ).toBe("这是一个非常长的消息，...");
  });
});
