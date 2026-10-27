"""Generate fictional Chinese internal-policy retrieval data, never real company rules."""

import argparse
import hashlib
import json
import random
from pathlib import Path


CITIES = ['北京', '上海', '杭州', '武汉', '成都', '南京', '苏州', '深圳', '西安', '合肥', '长沙', '厦门']
DEPARTMENTS = [
    ('检索平台组', '搜索团队'), ('推荐算法组', '推荐团队'), ('数据工程组', '数仓团队'),
    ('支付服务组', '支付团队'), ('订单系统组', '订单团队'), ('消息中间件组', '消息团队'),
    ('用户账户组', '账号团队'), ('内容处理组', '内容团队'), ('监控工具组', '可观测团队'),
    ('计算调度组', '算力团队'),
]
ENVIRONMENTS = [
    ('生产环境', ('线上正式服务', '已经对客开放的系统', '正在承接真实用户的服务')),
    ('预发布环境', ('上线前的仿真联调区', '正式切流前的验收区', '还没接真实流量的验证区')),
    ('开发环境', ('开发同学本地联调区', '写代码时自测的系统', '研发日常调试用的服务')),
]
# Query variants are authored before scoring; each split uses a different wording.
TOPICS = [
    ('临时访问授权', '身份申请单', '申请人填写访问用途和目标资源，经{reviewer}复核后发放短期只读权限，到期自动撤回。',
     ('临时进去看一下数据需要办什么手续', '只借用一下查看权限应该怎么申请', '想短时间查数据但没有访问资格，应该走什么流程')),
    ('版本交付', '版本变更单', '发布人上传制品摘要和回退版本，{reviewer}确认后逐批切换实例，观察异常率再扩大流量。',
     ('新版本准备发出去，怎么安排上线', '代码打好包之后如何交付到服务里', '功能写完了，怎样把新版安全地放到目标系统')),
    ('故障回退', '版本恢复单', '值班人停止继续切流并保留故障现场，由{reviewer}确认稳定版本，恢复后核对核心接口。',
     ('刚刚升级出了问题，怎样退回旧版', '新代码导致服务异常，要怎样撤销这次更新', '刚换上去的版本不工作了，恢复到之前那版要怎么办')),
    ('快照留存', '副本计划单', '维护人登记数据范围和恢复目标，由{reviewer}批准快照频率，副本写入隔离存储并定期抽检可读性。',
     ('如何安排数据副本，防止原件丢失', '想定期留下数据拷贝，应当怎样设置', '担心之后找不回数据，提前保留副本该如何操作')),
    ('历史数据恢复', '数据恢复单', '操作人指定恢复时点和目标空间，经{reviewer}确认后先还原到隔离实例，比对记录后再替换业务数据。',
     ('误删了记录，怎么把之前的数据找回来', '数据被改坏了，想恢复到昨天应该怎样做', '表里的内容弄丢了，找回旧记录应当走哪种流程')),
    ('访问凭据轮换', '密钥更换单', '服务负责人创建新凭据，经{reviewer}登记后让新旧凭据短暂并行，确认调用迁移完毕再作废旧值。',
     ('接口的秘密口令要换一套，该怎么做', '调用服务的认证串需要更新，要走什么步骤', '想把旧的鉴权口令停掉并启用新的，怎样平稳替换')),
    ('日志取证', '诊断记录单', '申请人提供请求标识与时间区间，经{reviewer}核准后导出脱敏诊断记录，禁止直接复制整库明细。',
     ('想查一次异常请求的详细记录，怎么获取', '排查报错需要调用轨迹，怎样取到那段记录', '某次请求失败了，要拿它发生时的运行记录该怎么办')),
    ('资源扩容', '容量调整单', '申请人提交负载曲线和容量估算，{reviewer}核准后增加实例配额，扩容完成需验证排队时间是否下降。',
     ('机器资源不够了，如何申请多给一点容量', '服务忙不过来，想多开一些实例怎么处理', '现有计算量扛不住请求，增加资源配额应该找什么流程')),
    ('数据对外提供', '数据交付单', '申请人填写接收方与最小字段集合，经{reviewer}检查授权范围后交付脱敏文件，并设置下载期限。',
     ('要把一份业务数据交给其他团队，怎么操作', '别的项目要我们提供数据文件，需要怎么审批', '准备把系统里的部分记录给外部协作方，应当办哪些手续')),
    ('闲置资源回收', '资产退役单', '资源所有者确认没有存量请求和依赖，由{reviewer}复核留存要求后回收实例，最后撤销网络及账户授权。',
     ('不用的服务和机器怎样彻底清掉', '项目结束后空着的资源该怎么释放', '有一批实例已经没有人使用了，退掉这些资源要按什么步骤')),
]
DOC_TEMPLATES = [
    '{team}／{environment}／{topic}。本范围通过“{form}”受理：{action}处理时限为{hours}小时。此条款仅适用于该团队的该环境。',
    '适用团队：{team}；适用空间：{environment}。事项：{topic}。执行规范：{action}请使用{form}，预计在{hours}小时内处理。本说明不覆盖其他团队或其他环境。',
    '内部操作手册：{team}在{environment}办理{topic}时，由{form}记录全过程。{action}受理窗口为{hours}小时。跨团队或跨环境须查各自对应条目。',
]
QUERY_TEMPLATES = [
    '我是{city}的{alias}同事，在{environment}，{question}？',
    '{city}{alias}这边遇到一个操作问题：{environment}，{question}？',
    '请帮我找{city}{alias}适用的办理说明：{environment}，{question}？',
]


def generate(seed=20261027):
    rng = random.Random(seed)
    teams = [(city, department, alias) for city in CITIES for department, alias in DEPARTMENTS]
    rng.shuffle(teams)
    data, metadata = {}, {'synthetic': True, 'seed': seed, 'teams': {}, 'facts': {},
                          'query_templates': {split: [QUERY_TEMPLATES[i]] for i, split in enumerate(['train','dev','test'])}}
    for split_index, split in enumerate(['train', 'dev', 'test']):
        selected = teams[split_index*40:(split_index+1)*40]
        metadata['teams'][split] = [city+department for city, department, _ in selected]
        facts = []
        for city, department, alias in selected:
            for env_index, (environment, environment_aliases) in enumerate(ENVIRONMENTS):
                for topic_index, (topic, form, action, questions) in enumerate(TOPICS):
                    fields = dict(team=city+department, city=city, alias=alias, topic=topic,
                                  environment=environment, form=form, hours=rng.choice([4, 8, 12, 24]),
                                  action=action.format(reviewer=rng.choice(['系统负责人', '当班运维', '资源所有者'])))
                    document = DOC_TEMPLATES[split_index].format(**fields)
                    query = QUERY_TEMPLATES[split_index].format(city=city, alias=alias,
                                                              environment=environment_aliases[split_index],
                                                              question=questions[split_index])
                    facts.append({'id': f'{split}-{city}-{department}-{env_index}-{topic_index}',
                                  'team': fields['team'], 'city': city, 'environment': environment,
                                  'topic': topic, 'document': document, 'query': query})
        rng.shuffle(facts)
        if split != 'train':
            facts = facts[:1000]
            data[split+'_corpus'] = [fact['document'] for fact in facts]
            # Sampling is fixed before any base or fine-tuned model is evaluated.
            queried = rng.sample(facts, 100)
        else:
            queried = facts
        data[split] = [{'query': fact['query'], 'positive': fact['document']} for fact in queried]
        metadata['facts'][split] = facts
    return data, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261027)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
            raise ValueError('Output directory must be new or empty')
        data, metadata = generate(args.seed)
        args.output.mkdir(parents=True, exist_ok=True)
        files = {}
        for name, rows in data.items():
            if name.endswith('_corpus'):
                rows = [{'text': text} for text in rows]
            path = args.output/f'{name}.jsonl'
            path.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows), encoding='utf-8')
            files[name] = {'rows':len(rows), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = {'synthetic': True, 'seed': args.seed, 'source': 'Hand-authored Chinese templates and seeded fictional policy slots; no external LLM/API.',
                    'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'split': '120 fictional city/department teams shuffled into40 train/40 dev/40 test; each team has10 topics x3 environments. Eval samples1000 documents and100 query facts per split.',
                    'isolation': 'Team identity and instantiated facts disjoint; query, topic paraphrase, environment paraphrase and document templates differ by split. Topic ontology and individual city/department tokens shared.',
                    'labels': 'Exactly one labeled positive per query: matching team, environment and operation. No IDs injected into retrieval text.',
                    'limitations': 'Template/slot synthetic benchmark; not natural user queries or real corporate policies. Shared topic ontology and limited wording can overstate transfer; no real-world improvement claim.',
                    'files': files, 'teams':metadata['teams']}
        (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        (args.output/'facts.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
