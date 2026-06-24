"""Django 管理命令：模型用量报告。"""

from django.core.management.base import BaseCommand

from mentora.model_gateway.ledger import aggregate_usage


class Command(BaseCommand):
    help = "输出模型 Token 用量与费用估算报告"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--task-type", type=str, default=None)
        parser.add_argument("--provider", type=str, default=None)

    def handle(self, *, days, task_type, provider, **options):
        report = aggregate_usage(
            days=days,
            task_type=task_type,
            provider=provider,
        )

        s = report["summary"]
        self.stdout.write(f"\n模型用量报告 ({days} 天)")
        self.stdout.write(f"  {report['start_date']} ~ {report['end_date']}\n")

        if s.get("requests", 0) == 0:
            self.stdout.write("  无数据")
            return

        self.stdout.write(f"  请求总数:    {s['requests']}")
        self.stdout.write(f"  成功率:      {s['success_rate_pct']}%")
        self.stdout.write(f"  Token 总量:  {s['total_tokens']:,}")
        self.stdout.write(f"  输入 Token:  {s['prompt_tokens']:,}")
        self.stdout.write(f"  输出 Token:  {s['completion_tokens']:,}")
        self.stdout.write(f"  费用估算:    ${s['cost_approx']}")
        self.stdout.write(f"  平均延迟:    {s['avg_latency_ms']}ms")
        self.stdout.write("")

        if report["by_task_type"]:
            self.stdout.write(self.style.SUCCESS("按任务类型:"))
            for row in report["by_task_type"]:
                self.stdout.write(
                    f"  {row['key']:12s} | {row['requests']:5d} 请求 "
                    f"| {row['success_rate_pct']:5.1f}% "
                    f"| {row['total_tokens']:>10,} tokens "
                    f"| ${row['cost_approx']:.2f}"
                )
            self.stdout.write("")

        if report["by_provider"]:
            self.stdout.write(self.style.SUCCESS("按 Provider:"))
            for row in report["by_provider"]:
                self.stdout.write(
                    f"  {row['key']:12s} | {row['requests']:5d} 请求 "
                    f"| {row['success_rate_pct']:5.1f}% "
                    f"| {row['total_tokens']:>10,} tokens "
                    f"| ${row['cost_approx']:.2f}"
                )
