#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from safe_xml import safe_fromstring


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".work"
OUT_FILE = OUT_DIR / "TED_Link_Based_English_Learning_10_Talks.epub"


@dataclass(frozen=True)
class Talk:
    topic: str
    title: str
    speaker: str
    event: str
    date: str
    plays: str
    url: str
    focus: str
    level: str
    korean_summary: list[str]
    english_summary: list[str]
    vocabulary: list[tuple[str, str, str]]
    phrases: list[tuple[str, str]]
    before_questions: list[str]
    after_questions: list[str]
    study_pairs: list[tuple[str, str]]


TALKS: list[Talk] = [
    Talk(
        topic="Education / Creativity",
        title="Do schools kill creativity?",
        speaker="Sir Ken Robinson",
        event="TED2006",
        date="February 2006",
        plays="80,259,579",
        url="https://www.ted.com/talks/sir_ken_robinson_do_schools_kill_creativity",
        focus="교육, 창의성, 유머 섞인 논증",
        level="Intermediate",
        korean_summary=[
            "학교가 아이들의 다양한 재능을 길러 주는 대신, 정답 중심의 틀 안에 가두는지를 묻는 강의다.",
            "연사는 창의성을 예술 과목의 부가 요소가 아니라 미래를 살아가는 핵심 능력으로 본다.",
            "유머와 일화가 많아, 주장-예시-반전의 흐름을 듣는 연습에 좋다.",
        ],
        english_summary=[
            "The talk challenges a narrow model of schooling and argues for a broader view of intelligence.",
            "It is useful for learning how a speaker builds a persuasive argument with humor and personal stories.",
        ],
        vocabulary=[
            ("creativity", "창의성", "Creativity is not limited to art; it also shapes problem solving."),
            ("nurture", "기르다, 양육하다", "Good education should nurture curiosity."),
            ("undermine", "약화시키다", "Too much fear of failure can undermine creativity."),
            ("curriculum", "교육과정", "A balanced curriculum respects different talents."),
        ],
        phrases=[
            ("make a case for", "~을 주장하다",),
            ("rather than", "~라기보다",),
            ("be afraid of being wrong", "틀리는 것을 두려워하다",),
        ],
        before_questions=[
            "학교에서 가장 창의적이라고 느꼈던 순간은 언제였나요?",
            "영어로 'education should...' 문장을 세 가지 만들어 보세요.",
        ],
        after_questions=[
            "연사가 유머를 사용해 청중의 긴장을 푸는 방식을 관찰하세요.",
            "강의의 중심 주장을 한 문장 영어로 요약하세요.",
        ],
        study_pairs=[
            ("교육은 아이들을 같은 모양으로 만들기보다 각자의 재능을 발견하게 도와야 한다.", "Education should help children discover their talents rather than make everyone fit the same mold."),
            ("창의성은 실수를 두려워하지 않는 분위기에서 자란다.", "Creativity grows in an atmosphere where people are not afraid to make mistakes."),
        ],
    ),
    Talk(
        topic="Leadership / Business",
        title="How great leaders inspire action",
        speaker="Simon Sinek",
        event="TEDxPuget Sound",
        date="September 2009",
        plays="70,453,262",
        url="https://www.ted.com/talks/simon_sinek_how_great_leaders_inspire_action",
        focus="리더십, 설득, why-how-what 구조",
        level="Intermediate",
        korean_summary=[
            "위대한 리더와 조직은 무엇을 하는지가 아니라 왜 하는지를 먼저 전달한다는 메시지의 강의다.",
            "브랜드, 운동, 발명가 이야기를 통해 추상적인 원칙을 구체적인 사례로 설명한다.",
            "비즈니스 영어와 발표 구조를 함께 익히기 좋다.",
        ],
        english_summary=[
            "The talk presents a simple framework for inspiring people by starting with purpose.",
            "It helps learners practice cause-and-effect language and persuasive repetition.",
        ],
        vocabulary=[
            ("inspire", "영감을 주다", "A clear purpose can inspire people to act."),
            ("purpose", "목적, 존재 이유", "Purpose is stronger than a list of features."),
            ("framework", "틀, 구조", "The speaker explains leadership through a simple framework."),
            ("differentiate", "차별화하다", "A strong why can differentiate a company."),
        ],
        phrases=[
            ("start with why", "왜에서 출발하다"),
            ("appeal to", "~에 호소하다"),
            ("take action", "행동에 나서다"),
        ],
        before_questions=[
            "좋아하는 브랜드 하나를 고르고, 그 브랜드의 why를 영어로 말해 보세요.",
            "내가 사람들을 설득할 때 what부터 말하는지 why부터 말하는지 생각해 보세요.",
        ],
        after_questions=[
            "연사가 반복하는 핵심 구조를 메모하세요.",
            "내 목표 하나를 why-how-what 순서로 영어 발표문처럼 정리하세요.",
        ],
        study_pairs=[
            ("사람들은 제품의 기능만이 아니라 그 제품이 상징하는 이유에 반응한다.", "People respond not only to a product's features but also to the reason it represents."),
            ("명확한 목적은 행동을 이끌어 내는 강력한 언어가 된다.", "A clear purpose becomes a powerful language for inspiring action."),
        ],
    ),
    Talk(
        topic="Psychology / Connection",
        title="The power of vulnerability",
        speaker="Brene Brown",
        event="TEDxHouston",
        date="June 2010",
        plays="70,594,037",
        url="https://www.ted.com/talks/brene_brown_the_power_of_vulnerability",
        focus="취약성, 공감, 인간관계",
        level="Upper-intermediate",
        korean_summary=[
            "취약함을 숨겨야 할 약점으로 보기보다, 관계와 용기의 출발점으로 바라보는 강의다.",
            "연구자의 분석과 개인적 고백이 섞여 있어 감정 어휘와 추상 개념을 배우기 좋다.",
            "듣는 동안 shame, belonging, courage 같은 단어가 어떤 맥락에서 쓰이는지 주목하면 좋다.",
        ],
        english_summary=[
            "The talk reframes vulnerability as a condition for connection and courage.",
            "It is especially useful for learning emotional vocabulary and reflective storytelling.",
        ],
        vocabulary=[
            ("vulnerability", "취약성, 약함을 드러내는 상태", "Vulnerability can be a source of courage."),
            ("connection", "연결, 유대", "Human connection is built through honesty."),
            ("belonging", "소속감", "Belonging is different from simply fitting in."),
            ("empathy", "공감", "Empathy requires listening without rushing to judge."),
        ],
        phrases=[
            ("open up", "마음을 열다"),
            ("let oneself be seen", "자신을 드러내다"),
            ("a sense of belonging", "소속감"),
        ],
        before_questions=[
            "vulnerability를 한국어 한 단어로만 옮기기 어려운 이유를 생각해 보세요.",
            "영어로 'I feel connected when...' 문장을 완성해 보세요.",
        ],
        after_questions=[
            "연사가 연구 이야기에서 개인 이야기로 넘어가는 지점을 찾아보세요.",
            "강의의 감정 어휘 5개를 골라 나만의 예문을 만드세요.",
        ],
        study_pairs=[
            ("취약함을 인정하는 일은 약해지는 것이 아니라 더 진실하게 연결되는 일이다.", "Acknowledging vulnerability is not becoming weak; it is becoming more honestly connected."),
            ("공감은 빠른 조언보다 먼저 조용히 듣는 능력에서 시작된다.", "Empathy begins with the ability to listen quietly before offering quick advice."),
        ],
    ),
    Talk(
        topic="Confidence / Body Language",
        title="Your body language may shape who you are",
        speaker="Amy Cuddy",
        event="TEDGlobal 2012",
        date="June 2012",
        plays="76,798,896",
        url="https://www.ted.com/talks/amy_cuddy_your_body_language_may_shape_who_you_are",
        focus="비언어 커뮤니케이션, 자신감, 연구 논쟁 읽기",
        level="Intermediate",
        korean_summary=[
            "몸짓이 다른 사람에게 주는 인상뿐 아니라 자기 인식에도 영향을 줄 수 있다는 주장을 다룬다.",
            "TED 페이지에는 해당 연구의 재현성 논쟁에 대한 주의문도 있어, 과학적 주장 읽기 연습에 적합하다.",
            "발표 영어에서는 may, might, can 같은 조심스러운 주장 표현을 관찰하면 좋다.",
        ],
        english_summary=[
            "The talk explores the relationship between posture, confidence and self-perception.",
            "It is useful for noticing cautious scientific language and claims under debate.",
        ],
        vocabulary=[
            ("posture", "자세", "Posture can influence how confident someone appears."),
            ("confidence", "자신감", "Confidence often changes how we speak."),
            ("robustness", "견고성", "Scientific findings are judged by their robustness."),
            ("reproducibility", "재현 가능성", "Reproducibility matters in scientific research."),
        ],
        phrases=[
            ("shape who we are", "우리가 어떤 사람인지 형성하다"),
            ("stand in a posture of confidence", "자신감 있는 자세를 취하다"),
            ("be referenced in a debate", "논쟁에서 언급되다"),
        ],
        before_questions=[
            "중요한 면접이나 발표 전에 내 몸짓이 어떻게 변하는지 떠올려 보세요.",
            "may, might, could의 뉘앙스 차이를 예문으로 정리하세요.",
        ],
        after_questions=[
            "강의에서 확정적 표현과 조심스러운 표현을 구분해 보세요.",
            "연구 논쟁이 있는 강의를 학습할 때 어떤 태도가 필요한지 영어로 쓰세요.",
        ],
        study_pairs=[
            ("자세는 우리가 자신을 바라보는 방식에도 영향을 줄 수 있다.", "Posture may influence the way we see ourselves."),
            ("과학적 주장은 매력적인 이야기뿐 아니라 재현 가능한 증거로도 평가되어야 한다.", "A scientific claim should be judged not only by an appealing story but also by reproducible evidence."),
        ],
    ),
    Talk(
        topic="Happiness / Work",
        title="The happy secret to better work",
        speaker="Shawn Achor",
        event="TEDxBloomington",
        date="May 2011",
        plays="27,227,364",
        url="https://www.ted.com/talks/shawn_achor_the_happy_secret_to_better_work",
        focus="행복, 생산성, 긍정심리학",
        level="Intermediate",
        korean_summary=[
            "성공하면 행복해진다는 순서를 뒤집어, 행복이 생산성과 성과를 돕는다는 관점을 제시한다.",
            "빠른 농담과 사례가 많아 리스닝 속도 적응에 좋다.",
            "비교, 반전, 인과관계를 표현하는 영어를 익히기 좋다.",
        ],
        english_summary=[
            "The talk argues that happiness can fuel better work rather than simply follow success.",
            "It is a useful listening exercise for fast humor and cause-and-effect reasoning.",
        ],
        vocabulary=[
            ("productive", "생산적인", "A positive mindset can make people more productive."),
            ("backwards", "거꾸로, 반대로", "We may be thinking about success and happiness backwards."),
            ("mindset", "사고방식", "Mindset shapes how we interpret challenges."),
            ("optimism", "낙관주의", "Optimism can affect motivation."),
        ],
        phrases=[
            ("think about things backwards", "문제를 거꾸로 생각하다"),
            ("fuel better work", "더 나은 일을 가능하게 하다"),
            ("positive mindset", "긍정적 사고방식"),
        ],
        before_questions=[
            "행복과 성공 중 어느 것이 먼저라고 생각하나요?",
            "영어로 'I work better when...' 문장을 세 가지 만들어 보세요.",
        ],
        after_questions=[
            "연사가 웃음을 이용해 핵심 주장으로 들어가는 방식을 관찰하세요.",
            "강의 내용을 바탕으로 내 하루 루틴을 영어로 5문장 써 보세요.",
        ],
        study_pairs=[
            ("행복은 성공 뒤에 오는 보상이 아니라 더 나은 일의 출발점일 수 있다.", "Happiness may be a starting point for better work, not just a reward after success."),
            ("우리가 문제를 해석하는 방식은 실제 성과에도 영향을 준다.", "The way we interpret problems can influence our actual performance."),
        ],
    ),
    Talk(
        topic="Personality / Culture",
        title="The power of introverts",
        speaker="Susan Cain",
        event="TED2012",
        date="February 2012",
        plays="36,182,734",
        url="https://www.ted.com/talks/susan_cain_the_power_of_introverts",
        focus="내향성, 문화, 개인의 강점",
        level="Intermediate",
        korean_summary=[
            "외향성이 높이 평가되는 문화 안에서 내향적인 사람이 가진 힘과 재능을 설명한다.",
            "성격, 사회적 기대, 개인의 에너지 관리에 관한 어휘를 익히기 좋다.",
            "차분한 발표 속도라 쉐도잉과 노트테이킹에 적합하다.",
        ],
        english_summary=[
            "The talk argues that introversion should be respected as a source of talent and depth.",
            "It is helpful for learning vocabulary about personality, culture and social expectations.",
        ],
        vocabulary=[
            ("introvert", "내향적인 사람", "An introvert may need quiet time to recharge."),
            ("outgoing", "사교적인, 외향적인", "Outgoing people often gain energy from groups."),
            ("solitude", "고독, 혼자 있는 시간", "Solitude can support deep thinking."),
            ("celebrate", "인정하고 기리다", "Different personalities should be celebrated."),
        ],
        phrases=[
            ("be prized above all else", "무엇보다 높이 평가되다"),
            ("bring talents to the world", "세상에 재능을 가져오다"),
            ("be encouraged and celebrated", "격려받고 인정받다"),
        ],
        before_questions=[
            "나는 혼자 있을 때 에너지가 차는 편인가, 사람들과 있을 때 차는 편인가요?",
            "introvert와 shy의 차이를 영어로 설명해 보세요.",
        ],
        after_questions=[
            "연사가 사회적 편견을 비판할 때 쓰는 표현을 찾아보세요.",
            "내 성격의 장점을 영어 자기소개 문장으로 바꿔 보세요.",
        ],
        study_pairs=[
            ("내향성은 고쳐야 할 결함이 아니라 다른 방식의 힘일 수 있다.", "Introversion can be a different kind of strength, not a flaw to be fixed."),
            ("조용한 시간은 깊이 생각하고 창의적으로 연결하는 데 도움이 된다.", "Quiet time helps people think deeply and connect ideas creatively."),
        ],
    ),
    Talk(
        topic="Motivation / Learning",
        title="Grit: The power of passion and perseverance",
        speaker="Angela Lee Duckworth",
        event="TED Talks Education",
        date="April 2013",
        plays="38,240,950",
        url="https://www.ted.com/talks/angela_lee_duckworth_grit_the_power_of_passion_and_perseverance",
        focus="끈기, 학습, 성장 사고방식",
        level="Intermediate",
        korean_summary=[
            "성공을 설명할 때 지능만으로는 부족하며, 장기적 목표를 향한 열정과 끈기가 중요하다는 강의다.",
            "교육 현장 경험과 연구 질문이 연결되어 있어 학습 동기 관련 영어에 좋다.",
            "short talk이라 반복 청취와 요약 훈련에 적합하다.",
        ],
        english_summary=[
            "The talk presents grit as a combination of passion and perseverance toward long-term goals.",
            "It is concise, making it useful for repeated listening and summary practice.",
        ],
        vocabulary=[
            ("grit", "끈기, 투지", "Grit is staying committed to long-term goals."),
            ("perseverance", "인내, 꾸준함", "Perseverance matters when progress is slow."),
            ("predictor", "예측 요인", "Grit can be a predictor of success."),
            ("long-term", "장기적인", "Long-term goals require patience."),
        ],
        phrases=[
            ("stick with", "~을 계속하다"),
            ("long-term goal", "장기 목표"),
            ("passion and perseverance", "열정과 끈기"),
        ],
        before_questions=[
            "내가 오래 지속해 온 목표 하나를 영어로 설명해 보세요.",
            "talent와 effort의 관계에 대한 내 생각을 한 문장으로 쓰세요.",
        ],
        after_questions=[
            "연사가 경험에서 연구 질문으로 넘어가는 지점을 찾아보세요.",
            "grit을 내 삶의 예시로 설명하는 영어 문단을 써 보세요.",
        ],
        study_pairs=[
            ("끈기는 재능이 부족할 때만 필요한 것이 아니라 장기 목표를 지탱하는 힘이다.", "Grit is not needed only when talent is lacking; it supports long-term goals."),
            ("느린 진전 속에서도 계속하는 능력이 학습의 방향을 바꿀 수 있다.", "The ability to continue despite slow progress can change the direction of learning."),
        ],
    ),
    Talk(
        topic="Communication / Speaking",
        title="How to speak so that people want to listen",
        speaker="Julian Treasure",
        event="TEDGlobal 2013",
        date="June 2013",
        plays="69,313,740",
        url="https://www.ted.com/talks/julian_treasure_how_to_speak_so_that_people_want_to_listen",
        focus="스피킹, 발성, 공감적 말하기",
        level="Intermediate",
        korean_summary=[
            "사람들이 듣고 싶어지는 말하기를 위해 피해야 할 습관과 연습 방법을 제시한다.",
            "영어 발표, 회의, 면접을 준비하는 학습자에게 바로 적용할 표현이 많다.",
            "발음보다 더 넓은 의미의 voice, tone, empathy를 함께 배울 수 있다.",
        ],
        english_summary=[
            "The talk offers practical advice on speaking with clarity, warmth and empathy.",
            "It is useful for learners who want to improve presentations and everyday communication.",
        ],
        vocabulary=[
            ("empathy", "공감", "Empathy makes communication more human."),
            ("clarity", "명확성", "Clarity helps listeners follow your message."),
            ("tone", "어조", "Tone can change how a message is received."),
            ("vocal", "목소리의, 발성의", "Vocal exercises can prepare a speaker."),
        ],
        phrases=[
            ("speak with empathy", "공감하며 말하다"),
            ("want to listen", "듣고 싶어 하다"),
            ("get your message across", "메시지를 전달하다"),
        ],
        before_questions=[
            "내 말하기에서 고치고 싶은 습관 하나를 영어로 써 보세요.",
            "좋은 발표자의 목소리에는 어떤 특징이 있나요?",
        ],
        after_questions=[
            "실제로 따라 할 수 있는 발성 연습을 하나 골라 보세요.",
            "내가 자주 쓰는 filler words를 영어로 점검하세요.",
        ],
        study_pairs=[
            ("좋은 말하기는 큰 목소리보다 명확한 의도와 공감에서 시작된다.", "Good speaking begins with clear intention and empathy rather than a loud voice."),
            ("청중이 듣고 싶어 하게 만들려면 먼저 그들이 이해할 수 있게 말해야 한다.", "To make people want to listen, you must first speak in a way they can understand."),
        ],
    ),
    Talk(
        topic="Health / Global Risk",
        title="The next outbreak? We're not ready",
        speaker="Bill Gates",
        event="TED2015",
        date="March 2015",
        plays="46,594,887",
        url="https://www.ted.com/talks/bill_gates_the_next_outbreak_we_re_not_ready",
        focus="보건, 위기 대비, 정책 영어",
        level="Upper-intermediate",
        korean_summary=[
            "전 세계가 감염병 대유행에 충분히 준비되어 있지 않다는 경고와 대비 체계를 설명하는 강의다.",
            "시나리오 계획, 백신 연구, 보건 인력 훈련 등 정책·과학 어휘를 익히기 좋다.",
            "위험을 과장하지 않으면서도 행동을 촉구하는 발표 방식을 관찰할 수 있다.",
        ],
        english_summary=[
            "The talk warns that global health systems need better preparation for outbreaks.",
            "It is useful for learning policy, health and risk-management vocabulary.",
        ],
        vocabulary=[
            ("outbreak", "질병 발생, 확산", "An outbreak can spread quickly across borders."),
            ("preparedness", "대비 태세", "Preparedness reduces the impact of crises."),
            ("vaccine", "백신", "Vaccine research requires long-term investment."),
            ("scenario planning", "시나리오 계획", "Scenario planning helps institutions respond faster."),
        ],
        phrases=[
            ("we're not ready", "우리는 준비되어 있지 않다"),
            ("put ideas into practice", "아이디어를 실행에 옮기다"),
            ("no need to panic", "당황할 필요는 없다"),
        ],
        before_questions=[
            "public health와 personal health의 차이를 영어로 설명해 보세요.",
            "위기 대비에 필요한 세 가지를 영어 명사로 적어 보세요.",
        ],
        after_questions=[
            "연사가 문제 제기에서 해결책으로 넘어가는 구조를 표시하세요.",
            "이 강의를 60초 정책 브리핑처럼 영어로 요약해 보세요.",
        ],
        study_pairs=[
            ("위험을 미리 준비하는 일은 공포를 키우는 것이 아니라 피해를 줄이는 일이다.", "Preparing for risk in advance does not create fear; it reduces harm."),
            ("보건 위기는 과학, 정책, 훈련이 함께 움직일 때 더 잘 대응할 수 있다.", "A health crisis can be handled better when science, policy and training work together."),
        ],
    ),
    Talk(
        topic="Data / Global Development",
        title="The best stats you've ever seen",
        speaker="Hans Rosling",
        event="TED2006",
        date="February 2006",
        plays="16,091,998",
        url="https://www.ted.com/talks/hans_rosling_the_best_stats_you_ve_ever_seen",
        focus="데이터 시각화, 세계 이해, 통계 영어",
        level="Upper-intermediate",
        korean_summary=[
            "통계와 시각화를 통해 개발도상국에 대한 고정관념을 깨는 강의다.",
            "데이터를 설명하는 영어, 비교급, 추세 묘사 표현을 익히기 좋다.",
            "숫자를 나열하는 대신 이야기처럼 보여 주는 발표 방식을 배울 수 있다.",
        ],
        english_summary=[
            "The talk uses animated data to challenge simplistic assumptions about global development.",
            "It is helpful for practicing trend language, comparisons and data storytelling.",
        ],
        vocabulary=[
            ("statistics", "통계", "Statistics can reveal patterns we might miss."),
            ("debunk", "틀렸음을 밝히다", "Good data can debunk a common myth."),
            ("trend", "추세", "A trend shows how something changes over time."),
            ("assumption", "가정, 전제", "Data can challenge our assumptions."),
        ],
        phrases=[
            ("present data", "데이터를 제시하다"),
            ("challenge assumptions", "가정을 흔들다"),
            ("over time", "시간이 지나면서"),
        ],
        before_questions=[
            "숫자와 그래프를 영어로 설명할 때 자주 필요한 동사를 적어 보세요.",
            "developing world라는 표현이 왜 단순할 수 있는지 생각해 보세요.",
        ],
        after_questions=[
            "강의에 나오는 추세 변화를 영어 문장으로 묘사하세요.",
            "데이터가 내 생각을 바꾸는 순간이 있었는지 한국어와 영어로 적어 보세요.",
        ],
        study_pairs=[
            ("좋은 데이터는 우리가 당연하다고 믿던 가정을 다시 보게 만든다.", "Good data makes us reexamine assumptions we once took for granted."),
            ("숫자는 이야기와 함께 제시될 때 더 설득력 있게 이해된다.", "Numbers become more persuasive when they are presented with a story."),
        ],
    ),
    Talk(
        topic="Productivity / Self-awareness",
        title="Inside the mind of a master procrastinator",
        speaker="Tim Urban",
        event="TED2016",
        date="February 2016",
        plays="78,463,679",
        url="https://www.ted.com/talks/tim_urban_inside_the_mind_of_a_master_procrastinator",
        focus="미루기, 시간관리, 유머러스한 자기분석",
        level="Intermediate",
        korean_summary=[
            "미루는 습관을 유머러스한 비유로 설명하면서, 정말 미루고 있는 일이 무엇인지 돌아보게 하는 강의다.",
            "일상적인 표현과 은유가 많아 영어식 농담과 자기고백 표현을 배우기 좋다.",
            "빠른 웃음 포인트보다 전체 구조를 잡으며 듣는 것이 중요하다.",
        ],
        english_summary=[
            "The talk uses humor and metaphor to explore procrastination and self-awareness.",
            "It is useful for learning casual storytelling, timing and reflective language.",
        ],
        vocabulary=[
            ("procrastinator", "일을 미루는 사람", "A procrastinator delays tasks even when they matter."),
            ("deadline", "마감일", "A deadline can create sudden urgency."),
            ("distraction", "주의를 빼앗는 것", "Digital distractions make focus harder."),
            ("self-awareness", "자기 인식", "Self-awareness helps us notice our habits."),
        ],
        phrases=[
            ("wait until the last minute", "마지막 순간까지 기다리다"),
            ("run out of time", "시간이 다 되다"),
            ("think harder about", "~에 대해 더 깊이 생각하다"),
        ],
        before_questions=[
            "내가 자주 미루는 일 하나를 영어로 써 보세요.",
            "deadline이 있을 때와 없을 때 내 행동이 어떻게 달라지는지 생각하세요.",
        ],
        after_questions=[
            "연사가 추상적 습관을 어떤 비유로 설명하는지 메모하세요.",
            "오늘 미루지 않을 작은 행동 하나를 영어로 선언하세요.",
        ],
        study_pairs=[
            ("미루기는 시간 관리의 문제일 뿐 아니라 자기 인식의 문제이기도 하다.", "Procrastination is not only a time-management problem but also a self-awareness problem."),
            ("마감일이 없는 목표일수록 더 의식적으로 시간을 설계해야 한다.", "Goals without deadlines require us to design our time more deliberately."),
        ],
    ),
]

SELECTED_TALKS = [talk for talk in TALKS if talk.title != "The best stats you've ever seen"]


def xml_escape(text: str) -> str:
    return html.escape(text, quote=True)


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def xhtml_page(title: str, body: str) -> str:
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ko" lang="ko">
<head>
  <title>{xml_escape(title)}</title>
  <meta charset="utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>
{body}
</body>
</html>
'''


def li_items(items: list[str]) -> str:
    return "\n".join(f"<li>{xml_escape(item)}</li>" for item in items)


def metadata_table(talk: Talk) -> str:
    rows = [
        ("주제", talk.topic),
        ("연사", talk.speaker),
        ("행사/시기", f"{talk.event}, {talk.date}"),
        ("TED 페이지 조회수", f"{talk.plays} plays"),
        ("학습 난이도", talk.level),
        ("듣기 포인트", talk.focus),
    ]
    return "<table>" + "\n".join(
        f"<tr><th>{xml_escape(k)}</th><td>{xml_escape(v)}</td></tr>" for k, v in rows
    ) + "</table>"


def talk_chapter(index: int, talk: Talk) -> tuple[str, str]:
    vocab_rows = "\n".join(
        f"<tr><td>{xml_escape(word)}</td><td>{xml_escape(ko)}</td><td>{xml_escape(example)}</td></tr>"
        for word, ko, example in talk.vocabulary
    )
    phrase_rows = "\n".join(
        f"<tr><td>{xml_escape(en)}</td><td>{xml_escape(ko)}</td></tr>"
        for en, ko in talk.phrases
    )
    pairs = "\n".join(
        f'''<p class="pair"><span class="ko">{xml_escape(ko)}</span><br />
<span class="en">{xml_escape(en)}</span></p>'''
        for ko, en in talk.study_pairs
    )
    body = f'''
  <section epub:type="chapter">
    <h1>{index}. {xml_escape(talk.title)}</h1>
    <p class="speaker">{xml_escape(talk.speaker)}</p>
    <p class="link"><a href="{xml_escape(talk.url)}">TED에서 강의 보기 / transcript 열기</a></p>

    <h2>기본 정보</h2>
    {metadata_table(talk)}

    <h2>한국어 핵심 요약</h2>
    <ul>{li_items(talk.korean_summary)}</ul>

    <h2>English Summary</h2>
    <ul>{li_items(talk.english_summary)}</ul>

    <h2>핵심 어휘</h2>
    <table>
      <tr><th>Word</th><th>뜻</th><th>새 예문</th></tr>
      {vocab_rows}
    </table>

    <h2>표현 덩어리</h2>
    <table>
      <tr><th>Expression</th><th>뜻</th></tr>
      {phrase_rows}
    </table>

    <h2>듣기 전 질문</h2>
    <ol>{li_items(talk.before_questions)}</ol>

    <h2>듣기 후 질문</h2>
    <ol>{li_items(talk.after_questions)}</ol>

    <h2>한영 연습문장</h2>
    {pairs}

    <h2>3회독 루틴</h2>
    <ol>
      <li>1회차: 자막 없이 전체 주제와 분위기만 잡기</li>
      <li>2회차: TED 페이지에서 transcript를 열어 모르는 표현 표시하기</li>
      <li>3회차: 이 장의 한영 연습문장을 소리 내어 말하고, 내 문장으로 바꾸기</li>
    </ol>
  </section>
'''
    filename = f"chapter{index:02d}-{slugify(talk.title)}.xhtml"
    return filename, xhtml_page(talk.title, body)


def build_nav(chapters: list[tuple[str, str]]) -> str:
    links = "\n".join(
        f'<li><a href="{xml_escape(filename)}">{xml_escape(title)}</a></li>'
        for filename, title in chapters
    )
    return xhtml_page(
        "목차",
        f'''
  <nav epub:type="toc" id="toc">
    <h1>목차</h1>
    <ol>
      <li><a href="intro.xhtml">사용 안내</a></li>
      {links}
      <li><a href="sources.xhtml">출처와 이용 안내</a></li>
    </ol>
  </nav>
''',
    )


def build_ncx(chapters: list[tuple[str, str]]) -> str:
    nav_points = [
        ("intro.xhtml", "사용 안내"),
        *chapters,
        ("sources.xhtml", "출처와 이용 안내"),
    ]
    points = "\n".join(
        f'''    <navPoint id="navPoint-{i}" playOrder="{i}">
      <navLabel><text>{xml_escape(title)}</text></navLabel>
      <content src="{xml_escape(filename)}"/>
    </navPoint>'''
        for i, (filename, title) in enumerate(nav_points, start=1)
    )
    return f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'ted-link-learning-10-talks')}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>TED 링크 기반 영어학습 노트</text></docTitle>
  <navMap>
{points}
  </navMap>
</ncx>
'''


def build_opf(manifest_items: list[tuple[str, str, str, str]]) -> str:
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    uid = uuid.uuid5(uuid.NAMESPACE_URL, "ted-link-learning-10-talks")
    manifest = "\n".join(
        f'    <item id="{item_id}" href="{xml_escape(href)}" media-type="{media_type}"{props}/>'
        for item_id, href, media_type, props in manifest_items
    )
    spine = "\n".join(
        f'    <itemref idref="{item_id}"/>'
        for item_id, href, media_type, props in manifest_items
        if media_type == "application/xhtml+xml" and item_id != "nav"
    )
    return f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ko">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{uid}</dc:identifier>
    <dc:title>TED 링크 기반 영어학습 노트: 인기 주제 10강</dc:title>
    <dc:creator>OpenAI Codex</dc:creator>
    <dc:language>ko</dc:language>
    <dc:date>{modified[:10]}</dc:date>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
{manifest}
  </manifest>
  <spine toc="ncx">
{spine}
  </spine>
</package>
'''


CSS = """@charset "utf-8";
html, body { margin: 0; padding: 0; }
body {
  font-family: serif;
  line-height: 1.58;
  word-break: keep-all;
  -webkit-hyphens: none;
  hyphens: none;
}
section { margin: 0; padding: 0; }
h1 {
  font-size: 1.55em;
  line-height: 1.25;
  margin: 1.4em 0 0.9em;
  text-align: center;
  page-break-before: always;
}
h2 {
  font-size: 1.12em;
  margin: 1.25em 0 0.45em;
  border-bottom: 1px solid #b8b8b8;
}
p { margin: 0 0 0.65em; text-indent: 0; }
ul, ol { padding-left: 1.35em; }
li { margin: 0.25em 0; }
table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.6em 0 0.9em;
}
th, td {
  border: 1px solid #b8b8b8;
  padding: 0.32em;
  vertical-align: top;
}
th { background: #eeeeee; }
a { color: inherit; text-decoration: underline; }
.cover {
  min-height: 90vh;
  display: block;
  margin: 18% 8% 0;
  text-align: center;
}
.cover h1 { page-break-before: auto; font-size: 2em; }
.subtitle { margin-top: 1.2em; }
.speaker { text-align: center; font-weight: bold; }
.link { text-align: center; margin-bottom: 1em; }
.notice {
  border: 1px solid #999999;
  padding: 0.6em;
  margin: 1em 0;
}
.pair { margin-bottom: 0.8em; }
.pair .ko { font-weight: bold; }
.pair .en { color: #444444; }
nav#toc h1 { page-break-before: auto; }
"""


def cover_page() -> str:
    return xhtml_page(
        "TED 링크 기반 영어학습 노트",
        """
  <section class="cover" epub:type="cover">
    <h1>TED 링크 기반 영어학습 노트</h1>
    <p class="subtitle">인기 주제 10강 / Korean-English Study Edition</p>
    <p>원문 스크립트 전문을 수록하지 않고 TED 공식 링크와 학습 노트로 구성했습니다.</p>
  </section>
""",
    )


def intro_page() -> str:
    return xhtml_page(
        "사용 안내",
        """
  <section epub:type="introduction">
    <h1>사용 안내</h1>
    <p class="notice">이 EPUB는 영어학습용 링크 노트입니다. TED 원문 transcript 전문이나 전체 번역을 포함하지 않습니다. 각 장의 링크를 열어 공식 TED 페이지에서 강의를 보고, 이 노트로 요약·어휘·질문 복습을 하세요.</p>
    <h2>추천 학습 순서</h2>
    <ol>
      <li>장마다 먼저 한국어 요약과 영어 요약을 읽습니다.</li>
      <li>TED 링크를 열어 강의를 자막 없이 1회 시청합니다.</li>
      <li>TED 페이지의 transcript를 열어 모르는 단어를 확인합니다.</li>
      <li>이 EPUB의 한영 연습문장을 소리 내어 읽고, 같은 구조로 내 문장을 만듭니다.</li>
    </ol>
    <h2>구성 원칙</h2>
    <ul>
      <li>각 강의는 공식 TED 페이지 제목, 연사, 행사, 날짜, 조회수를 기준으로 정리했습니다.</li>
      <li>요약과 예문은 학습용으로 새로 작성했습니다.</li>
      <li>저작권 보호를 위해 transcript 전문과 전체 번역은 포함하지 않았습니다.</li>
    </ul>
  </section>
""",
    )


def sources_page() -> str:
    talk_links = "\n".join(
        f'<li><a href="{xml_escape(talk.url)}">{xml_escape(talk.title)} - {xml_escape(talk.speaker)}</a></li>'
        for talk in SELECTED_TALKS
    )
    return xhtml_page(
        "출처와 이용 안내",
        f"""
  <section epub:type="appendix">
    <h1>출처와 이용 안내</h1>
    <p>모든 강의 정보는 TED 공식 페이지를 기준으로 정리했습니다. TED Talks는 TED의 이용 정책과 Creative Commons BY-NC-ND 조건을 따르므로, 이 EPUB에는 원문 transcript 전문이나 번역 전문을 넣지 않았습니다.</p>
    <h2>공식 TED 링크</h2>
    <ol>
      {talk_links}
    </ol>
    <h2>TED 이용 정책</h2>
    <p><a href="https://www.ted.com/about/our-organization/our-policies-terms/ted-talks-usage-policy">TED Talks Usage Policy</a></p>
  </section>
""",
    )


def write_epub(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": b'''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
''',
        "OEBPS/styles.css": CSS.encode("utf-8"),
        "OEBPS/cover.xhtml": cover_page().encode("utf-8"),
        "OEBPS/intro.xhtml": intro_page().encode("utf-8"),
        "OEBPS/sources.xhtml": sources_page().encode("utf-8"),
    }

    chapter_refs: list[tuple[str, str]] = []
    for index, talk in enumerate(SELECTED_TALKS, start=1):
        filename, page = talk_chapter(index, talk)
        files[f"OEBPS/{filename}"] = page.encode("utf-8")
        chapter_refs.append((filename, f"{index}. {talk.title}"))

    files["OEBPS/nav.xhtml"] = build_nav(chapter_refs).encode("utf-8")
    files["OEBPS/toc.ncx"] = build_ncx(chapter_refs).encode("utf-8")

    manifest_items: list[tuple[str, str, str, str]] = [
        ("nav", "nav.xhtml", "application/xhtml+xml", ' properties="nav"'),
        ("ncx", "toc.ncx", "application/x-dtbncx+xml", ""),
        ("style", "styles.css", "text/css", ""),
        ("cover", "cover.xhtml", "application/xhtml+xml", ""),
        ("intro", "intro.xhtml", "application/xhtml+xml", ""),
    ]
    for i, (filename, _) in enumerate(chapter_refs, start=1):
        manifest_items.append((f"chapter{i:02d}", filename, "application/xhtml+xml", ""))
    manifest_items.append(("sources", "sources.xhtml", "application/xhtml+xml", ""))
    files["OEBPS/content.opf"] = build_opf(manifest_items).encode("utf-8")

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", files.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        for name, data in files.items():
            zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def validate_epub(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if names[:1] != ["mimetype"]:
            raise RuntimeError("mimetype is not first")
        for name in names:
            if name.lower().endswith((".xhtml", ".opf", ".ncx")):
                safe_fromstring(zf.read(name))


def main() -> int:
    write_epub(OUT_FILE)
    validate_epub(OUT_FILE)
    print(OUT_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
