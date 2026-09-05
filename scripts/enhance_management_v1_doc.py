#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from kiwipiepy import Kiwi


DEFAULT_INPUT = Path(
    str(Path.home()) + "/Desktop/1차 시험/#STD/260416/management_OX_integrated_2026_v1.docx"
)
KIWI = Kiwi()

SECTION_ORDER = [
    "경영일반·전략",
    "조직행동·인사",
    "마케팅",
    "생산·운영관리",
    "재무·회계",
    "기타",
]

SECTION_NOTES = {
    "경영일반·전략": "경영전략은 거의 매년 반복되는 점수원이다. 포터, BCG, 가치사슬, 제품·시장 매트릭스처럼 대표 모형의 정의와 위치를 정확히 외우는 것이 중요하다.",
    "조직행동·인사": "인사·조직은 2차 인사노무관리론·경영조직론과 직접 연결된다. 개념 구분과 학자 연결이 핵심이므로 용어를 비교식으로 정리하는 것이 좋다.",
    "마케팅": "마케팅은 이해형 파트지만, 표적시장 전략·4P·소비자행동처럼 용어를 조금만 바꾸면 헷갈리기 쉽다. 개념 간 경계를 정확히 잡아야 한다.",
    "생산·운영관리": "운영관리는 생소한 개념과 가벼운 계산이 섞여 나온다. 생산관리 이론과 MIS 기본 상식을 구분해 정리하면 효율적이다.",
    "재무·회계": "재무·회계는 계산형과 개념형이 함께 나오며, 수험생이 가장 부담을 느끼는 파트다. 빈출 개념과 대표 계산 유형을 먼저 고정해야 한다.",
    "기타": "기타 파트는 여러 세부 영역이 섞인 만큼 지문마다 핵심 키워드를 먼저 잡는 연습이 중요하다.",
}

SECTION_GUIDES = {
    "경영일반·전략": {
        "key": "전략 파트는 모형의 정의, 구성요소, 위치를 정확히 구분하는 것이 핵심이다.",
        "memory": "포터, BCG, 가치사슬처럼 대표 모형은 이름-목적-구성요소를 세 칸으로 나눠 외우면 빠르다.",
        "related": "원가우위·차별화·집중전략, 시장성장률·상대적 시장점유율처럼 자주 비교되는 축을 함께 묶어 둔다.",
    },
    "조직행동·인사": {
        "key": "조직행동·인사는 개념 구분과 학자 연결, 제도별 목적과 효과를 정확히 구분하는 것이 핵심이다.",
        "memory": "동기부여, 리더십, 조직구조, 평가·보상은 '누가 무엇을 설명했는지'와 '무슨 효과를 노리는지'를 같이 적어 두면 기억이 쉽다.",
        "related": "2차 인사노무관리론·경영조직론과 연결되므로 학자명과 핵심 키워드를 함께 정리하면 누적 효과가 크다.",
    },
    "마케팅": {
        "key": "마케팅은 시장세분화, 표적시장, 포지셔닝, 4P, 소비자행동의 경계를 정확히 구분하는 것이 핵심이다.",
        "memory": "마케팅은 '누구에게 무엇을 어떻게 팔 것인가' 순서로 읽으면 개념이 정리된다.",
        "related": "제품·가격·유통·촉진은 각각 어떤 의사결정과 연결되는지 함께 묶어 두면 응용형에도 강해진다.",
    },
    "생산·운영관리": {
        "key": "생산·운영관리는 생산관리 개념과 MIS·IT 기본 상식을 구분해서 보는 것이 핵심이다.",
        "memory": "운영관리 문제는 '공정·재고·품질·정보시스템' 중 어느 축인지 먼저 표시하면 헷갈림이 줄어든다.",
        "related": "재고모형, 품질관리, 공정배치, MRP, ERP, MIS 약어는 함께 묶어 두면 회독이 편하다.",
    },
    "재무·회계": {
        "key": "재무·회계는 계산식 자체보다 개념의 의미, 지표의 방향, 계정과목의 분류를 정확히 아는 것이 핵심이다.",
        "memory": "공식은 무작정 외우기보다 '무엇을 분자에 두고 무엇을 분모에 두는지'를 말로 설명해 보면 오래 남는다.",
        "related": "재무관리는 기업가치·현금흐름·투자안 평가와 연결되고, 회계는 계정 분류와 재무제표 구조를 함께 봐야 한다.",
    },
    "기타": {
        "key": "낯선 지문일수록 핵심 키워드와 그 개념 범위를 먼저 잡는 것이 중요하다.",
        "memory": "지문 속 영문 약어, 학자명, 모형명을 먼저 표시하면 선택지가 훨씬 빨리 정리된다.",
        "related": "세부 영역이 달라도 핵심 개념의 정의와 적용 범위를 비교하는 습관이 가장 도움이 된다.",
    },
}

SECTION_EXAMPLES = {
    "경영일반·전략": "예를 들어 포터의 본원전략에서 경험효과와 규모의 경제는 비용을 낮추는 축이므로 원가우위 전략으로 연결해야 한다.",
    "조직행동·인사": "예를 들어 허즈버그의 동기요인과 위생요인은 둘 다 중요하지만, 만족을 높이는 요인과 불만을 줄이는 요인을 구별해야 한다.",
    "마케팅": "예를 들어 같은 제품이라도 표적고객을 누구로 잡느냐에 따라 포지셔닝과 4P 전략이 달라진다.",
    "생산·운영관리": "예를 들어 재고관리 문제는 주문 시점과 주문 수량을, MIS 문제는 정보기술 용어의 정확한 뜻을 묻는 식으로 출제된다.",
    "재무·회계": "예를 들어 유동자산과 비유동자산, 비용과 자산처럼 분류 기준을 먼저 잡으면 계산문제도 훨씬 덜 흔들린다.",
    "기타": "예를 들어 낯선 경영학 모형이 나와도 이름, 목적, 구성요소 세 칸으로 나누면 빠르게 정리된다.",
}

ISSUE_SPECIFIC_GUIDES = (
    (
        re.compile(r"(경험효과|규모의 경제|투입 요소 비용|생산시설활용도)"),
        {
            "key": "원가우위 전략은 비용을 낮추는 원천이 무엇인지 정확히 구분하는 것이 핵심이다.",
            "memory": "경험효과, 규모의 경제, 투입 요소 비용, 생산시설활용도는 모두 '원가를 내리는 축'으로 묶어 외우면 쉽다.",
            "related": "차별화 전략은 제품 특성, 브랜드, 포지셔닝, 서비스처럼 고객이 인식하는 가치를 높이는 요소와 연결해 둔다.",
        },
    ),
    (
        re.compile(r"(차별화|제품의 특성|포지셔닝|브랜드)"),
        {
            "key": "차별화 전략은 고객이 체감하는 독자적 가치가 무엇인지 정확히 구분하는 것이 핵심이다.",
            "memory": "차별화는 '비용 절감'이 아니라 '고객이 다르게 느끼는 가치'라고 먼저 외우면 정리가 쉽다.",
            "related": "원가우위 전략과 비교해 보면, 차별화는 가격이 아니라 제품 특성·브랜드·서비스에서 경쟁력이 나온다는 점이 선명해진다.",
        },
    ),
    (
        re.compile(r"(가치사슬|입고·출고|운영·제조|고객 서비스|영업·마케팅|인적자원관리)"),
        {
            "key": "가치사슬은 주요 활동과 지원 활동을 정확히 나누는 것이 핵심이다.",
            "memory": "가치사슬은 '들여오고-만들고-내보내고-팔고-서비스'를 주요 활동으로 먼저 외우면 빠르다.",
            "related": "인적자원관리, 기술개발, 조달, 기업하부구조는 지원 활동으로 따로 묶어 둔다.",
        },
    ),
    (
        re.compile(r"(조직문화|의례 의식|상징|이야기|권력|전술|가치와 전략에 대한 구성원의 몰입|전략적 상황 요인 충족)"),
        {
            "key": "조직문화와 권력 파트는 개념의 기능과 전술의 목적을 정확히 구분하는 것이 핵심이다.",
            "memory": "문화는 '공유된 의미', 권력 전술은 '영향력 행사 방법'으로 나눠 외우면 덜 헷갈린다.",
            "related": "조직문화 강화 수단과 권력 강화 전술은 표현이 비슷해도 기능이 다르므로 함께 비교해 둔다.",
        },
    ),
    (
        re.compile(r"(동기부여|리더십|브룸|허즈버그|매슬로|맥그리거|기대이론)"),
        {
            "key": "동기부여와 리더십은 이론별 핵심 가정과 설명 대상을 구분하는 것이 핵심이다.",
            "memory": "학자 이론은 '누가-무엇을-어떻게 설명하는지' 세 칸으로 정리하면 기억이 쉽다.",
            "related": "내용이론과 과정이론, 리더 특성과 상황이론은 묶어서 비교하는 편이 좋다.",
        },
    ),
    (
        re.compile(r"(4P|제품|가격|유통|촉진|포지셔닝|표적시장|시장세분화|소비자행동)"),
        {
            "key": "마케팅은 STP와 4P, 소비자행동 개념의 경계를 정확히 구분하는 것이 핵심이다.",
            "memory": "마케팅은 '누구에게-STP / 무엇을 어떻게-4P'로 나눠 외우면 정리가 쉽다.",
            "related": "시장세분화 기준, 포지셔닝, 제품수명주기, 구매의사결정 과정을 함께 연결해 두면 좋다.",
        },
    ),
    (
        re.compile(r"(재고|품질|MRP|ERP|MIS|USB|공정|생산관리|운영관리)"),
        {
            "key": "생산·운영관리는 공정, 재고, 품질, 정보시스템 개념을 정확히 구분하는 것이 핵심이다.",
            "memory": "운영관리 문제는 '생산관리인지 정보시스템인지'부터 먼저 구분하면 판단이 빨라진다.",
            "related": "EOQ, 품질관리 기법, 공정배치, ERP·MRP·MIS 약어를 함께 묶어 두는 편이 좋다.",
        },
    ),
    (
        re.compile(r"(재무제표|회계|NPV|IRR|현금흐름|자본비용|계정과목|재무관리|투자론|파생상품)"),
        {
            "key": "재무·회계는 지표의 의미, 계정 분류, 투자안 평가 기준을 정확히 구분하는 것이 핵심이다.",
            "memory": "공식은 숫자보다 '무엇을 비교하는 지표인지'를 말로 설명해 보면 오래 남는다.",
            "related": "재무제표 구조, 현금흐름, 자본비용, 투자안 평가, 계정과목 분류를 함께 연결해 두면 좋다.",
        },
    ),
)

SECTION_MNEMONICS = {
    "경영일반·전략": {"tag": "#모목구", "tip": "모형-목적-구성요소의 세 칸으로 나눠 외우면 전략 파트가 가장 빨리 정리된다."},
    "조직행동·인사": {"tag": "#학효구", "tip": "학자-효과-구조를 같이 적어 두면 조직행동과 인사가 오래 남는다."},
    "마케팅": {"tag": "#세표포4", "tip": "세분화-표적시장-포지셔닝 다음에 4P를 붙여 외우면 마케팅 전체 틀이 선다."},
    "생산·운영관리": {"tag": "#공재품정", "tip": "공정-재고-품질-정보시스템 순으로 나눠 외우면 운영관리 파트가 쉬워진다."},
    "재무·회계": {"tag": "#재현자투", "tip": "재무제표-현금흐름-자본비용-투자안 평가를 한 줄로 묶으면 기본 틀이 잡힌다."},
    "기타": {"tag": "#정구범", "tip": "정의-구성요소-범위를 먼저 적는 습관이 경영학 OX 회독에 가장 효율적이다."},
}

ISSUE_MNEMONICS = (
    (re.compile(r"(경험효과|규모의 경제|투입 요소 비용|생산시설활용도)"), {"tag": "#경규투생", "tip": "경험효과-규모의 경제-투입 요소 비용-생산시설활용도는 모두 원가우위의 원천이라고 묶어 외운다."}),
    (re.compile(r"(차별화|제품의 특성|포지셔닝|브랜드)"), {"tag": "#제브포서", "tip": "제품 특성-브랜드-포지셔닝-서비스처럼 고객이 느끼는 가치 중심으로 외우면 차별화가 잘 남는다."}),
    (re.compile(r"(가치사슬|입고·출고|운영·제조|고객 서비스|영업·마케팅|인적자원관리)"), {"tag": "#입운출영서", "tip": "입고-운영-출고-영업-서비스를 주요 활동으로 먼저 외우고, 지원 활동은 따로 묶는다."}),
    (re.compile(r"(조직문화|의례 의식|상징|이야기|권력|전술|가치와 전략에 대한 구성원의 몰입|전략적 상황 요인 충족)"), {"tag": "#공영전", "tip": "공유된 의미-영향력-전술의 차이를 대비해서 읽으면 조직문화와 권력 문제가 빨라진다."}),
    (re.compile(r"(동기부여|리더십|브룸|허즈버그|매슬로|맥그리거|기대이론)"), {"tag": "#누무어", "tip": "누가-무엇을-어떻게 설명하는 이론인지 세 칸으로 정리해 외운다."}),
    (re.compile(r"(4P|제품|가격|유통|촉진|포지셔닝|표적시장|시장세분화|소비자행동)"), {"tag": "#세표포4", "tip": "세분화-표적시장-포지셔닝을 먼저 외우고 그 뒤에 4P를 붙이면 마케팅 전체가 묶인다."}),
    (re.compile(r"(재고|품질|MRP|ERP|MIS|USB|공정|생산관리|운영관리)"), {"tag": "#공재품정", "tip": "공정-재고-품질-정보시스템 네 축으로 나눠 보면서 약어는 따로 반복해서 읽는다."}),
    (re.compile(r"(재무제표|회계|NPV|IRR|현금흐름|자본비용|계정과목|재무관리|투자론|파생상품)"), {"tag": "#재현자투", "tip": "재무제표-현금흐름-자본비용-투자안 평가 순으로 정리하면 재무·회계 기본틀이 오래 남는다."}),
)

GENERIC_EXPLANATION_PATTERNS = (
    r"같은 기출문항에서 옳은 진술로 기능하는 문장을 그대로 OX화한 것이다\.\s*",
    r"이 진술은 같은 쟁점의 기준 문언·판례 결론과 맞지 않는다\.\s*",
    r"전략 파트는 개념구분형과 이론가·모형형 함정이 자주 나온다\.\s*",
    r"원가우위·차별화·집중전략을 서로 바꾸는 문제가 대표적이다\.\s*",
    r"핵심 개념의 경계를 흐리게 하는 기본형 함정이 많으니 정의를 짧게라도 정확히 외우는 것이 좋다\.\s*",
    r"용어 하나만 바꾼 기본형 OX도 꾸준히 출제되므로 핵심 키워드를 정확히 기억해야 한다\.\s*",
)

FOCUS_STOPWORDS = {
    "경영학", "개론", "기준", "문제", "지문", "설명", "개념", "내용", "정의",
    "전략", "관리", "조직", "경우",
}

MANUAL_X_RULES = (
    (
        re.compile(r"경험효과는 차별화 전략의 원천"),
        "정답은 X입니다. 경험효과는 차별화 전략이 아니라 원가우위 전략의 대표적 원천이다.",
    ),
    (
        re.compile(r"규모의 경제는 차별화 전략의 원천"),
        "정답은 X입니다. 규모의 경제는 차별화 전략이 아니라 원가우위 전략의 대표적 원천이다.",
    ),
    (
        re.compile(r"투입 요소 비용은 차별화 전략의 원천"),
        "정답은 X입니다. 투입 요소 비용은 차별화 전략이 아니라 원가우위 전략의 대표적 원천이다.",
    ),
    (
        re.compile(r"생산시설활용도는 차별화 전략의 원천"),
        "정답은 X입니다. 생산시설활용도는 차별화 전략이 아니라 원가우위 전략의 대표적 원천이다.",
    ),
)

DIRECT_REPLACEMENTS = {
    "생산 시설 활용 도": "생산시설활용도",
    "제품/ 시장": "제품/시장",
    "영업·마케팅": "영업·마케팅",
    "입고·출고": "입고·출고",
    "수익 관리": "수익관리",
    "재무 관리": "재무관리",
    "재무 회계": "재무회계",
    "관리 회계": "관리회계",
    "인적 자원 관리": "인적자원관리",
    "조직 행동론": "조직행동론",
    "생산 관리": "생산관리",
    "운영 관리": "운영관리",
    "경영 전략": "경영전략",
    "마케팅 관리론": "마케팅관리론",
    "회계 관리론": "회계관리론",
    "재무 관리론": "재무관리론",
    "투자 론": "투자론",
    "문 제": "문제",
    "계 산": "계산",
    "기 출": "기출",
}

REGEX_REPLACEMENTS = (
    (r"가치\s*사슬", "가치사슬"),
    (r"차별화\s*전략", "차별화 전략"),
    (r"원가\s*우위", "원가우위"),
    (r"집중\s*전략", "집중전략"),
    (r"재무\s*회계", "재무회계"),
    (r"재무\s*관리", "재무관리"),
    (r"경영학\s*개론", "경영학개론"),
    (r"생산\s*운영관리", "생산운영관리"),
    (r"기업\s*가치", "기업가치"),
    (r"자금\s*젖소", "자금젖소"),
    (r"문제\s*해결", "문제해결"),
)

SUMMARY_ROWS = [
    ("인사/조직", "62", "31.0%", "21", "26.3%"),
    ("재무/회계", "43", "24.0%", "21", "26.3%"),
    ("마케팅", "33", "16.5%", "10", "12.5%"),
    ("운영관리", "27", "15.0%", "13", "16.3%"),
    ("경영전략", "27", "13.5%", "15", "18.8%"),
]

HR_POINTS = [
    "인사/조직 분야는 2차 필수과목인 인사노무관리론, 선택과목인 경영조직론과 상당 부분 중복되므로 1차와 2차를 함께 준비하는 가장 효율적인 파트다.",
    "조직행동론은 개인·집단·조직 차원을 구분해서 보고, 인사관리론은 모집·선발·평가·보상·교육훈련 등 흐름으로 정리하는 것이 좋다.",
    "충분한 시간을 투자하면 1차 점수 확보뿐 아니라 2차까지 연결되는 누적효과가 크다.",
]

FINANCE_POINTS = [
    "재무/회계는 공부량이 많고 계산문제 비중도 높아 대부분의 수험생이 가장 부담스러워하는 파트다.",
    "고득점이 목표가 아니라면 모든 계산을 다 잡기보다 빈출 개념과 반복되는 계산 유형을 먼저 고정하는 전략이 더 효율적이다.",
    "과락 방지 또는 평균 점수 확보가 목표라면 10~12문제 중 6문제 이상 확보를 목표로 하고, 기본 개념형을 최대한 놓치지 않는 것이 중요하다.",
]

MARKETING_POINTS = [
    "마케팅은 마케팅 전략과 마케팅 믹스, 그리고 최근에는 소비자행동론까지 연결되는 방식으로 출제된다.",
    "무작정 암기하기보다 시장세분화, 표적시장, 포지셔닝, 4P, 소비자행동 핵심 용어를 정확히 구분하는 것이 중요하다.",
]

OPERATIONS_POINTS = [
    "운영관리는 생산관리론과 MIS를 포함하며, 문과계열 수험생에게는 상대적으로 생소할 수 있다.",
    "생산관리에서는 경영혁신, 품질, 재고, 공정 관련 문제가 반복되고, MIS는 최근 IT 기본상식이나 약어형 지문이 자주 출제되는 편이다.",
]

GENERAL_POINTS = [
    "경영일반·전략은 반복 출제가 가장 강한 점수원 파트다. BCG 매트릭스, 포터의 경쟁전략, 계획 수립, 기업 형태, 경영학 일반 이론은 거의 매년 다시 나온다고 보고 준비하는 편이 좋다.",
    "기출문제 수준에서 반복되는 문제가 많으므로, 70~80점 목표 전략에서는 반드시 안정적으로 득점해야 하는 영역이다.",
]

FINAL_POINTS = [
    "문항 수가 40문항으로 늘어난 뒤에는 경영학 전반을 넓게 보는 시야가 중요해졌다. 깊이보다 폭이 중요한 문제가 늘었기 때문이다.",
    "다만 지엽적인 문제에 과도하게 매달리기보다, 언제나 반복 출제되는 핵심 영역을 확실히 가져가고 최근 타 시험 기출로 변형 감각을 익히는 편이 더 효율적이다.",
    "경영학개론은 2차 인사노무관리론·경영조직론과 연결되는 장점이 크므로, 1차 공부를 단순 점수 확보가 아니라 2차 기초 축적의 기회로 활용하는 것이 좋다.",
]

TRAP_MEMORY_ROWS = [
    (
        "인사·조직 동기이론 구분",
        "매슬로우, 허즈버그, 맥그리거, 브룸처럼 이름이 비슷하게 섞이는 이론은 전제와 초점을 구분해야 한다.",
        "#욕위공기",
        "욕구-위생-공정-기대처럼 핵심 단어 하나씩만 붙여 외우면 긴 지문 속에서도 이론을 빨리 판별할 수 있다.",
    ),
    (
        "평가·보상 제도",
        "직무평가, 성과평가, 보상, 인센티브는 기준과 목적이 다르므로 한 번에 섞어 내는 문제가 많다.",
        "#직성보인",
        "직무-성과-보상-인센티브를 표로 놓고 '무엇을 기준으로 삼는가'만 먼저 비교하면 효율적이다.",
    ),
    (
        "재무·회계 핵심 틀",
        "재무상태표, 손익계산서, 현금흐름표, 자본변동표의 기능과 연결 관계를 구분해야 한다.",
        "#재손현자",
        "재무-손익-현금-자본 순서로 큰 그림을 먼저 잡고, 각 표가 무엇을 보여 주는지만 반복하면 기본기가 빨리 선다.",
    ),
    (
        "투자안 의사결정",
        "NPV, IRR, 회수기간, 할인율은 서로 비교해서 출제되므로 개념과 판단 기준을 함께 알아야 한다.",
        "#순내회할",
        "순현재가치-내부수익률-회수기간-할인율을 한 세트로 외우고, '채택 기준이 무엇인지'를 같이 적어 두면 좋다.",
    ),
    (
        "마케팅 STP와 4P",
        "시장세분화, 표적시장, 포지셔닝, 제품·가격·유통·촉진을 뒤섞는 문제가 반복된다.",
        "#세표포4",
        "세분화-표적화-포지셔닝을 먼저 말한 뒤 바로 4P를 이어 붙이면 전략과 실행이 함께 기억된다.",
    ),
    (
        "운영관리 계산·혁신",
        "재고, 품질, 공정, 경영혁신은 계산형과 개념형이 섞여 나온다.",
        "#재품공혁",
        "재고-품질-공정-혁신 순으로 분류표를 만들고, 계산식은 재고와 품질 위주로 반복하는 전략이 효율적이다.",
    ),
    (
        "전략 이론 구분",
        "포터 경쟁전략, 가치사슬, BCG 매트릭스, 제품수명주기처럼 도식형 이론은 표현을 바꿔 함정을 만든다.",
        "#포가비수",
        "포터-가치사슬-BCG-수명주기 네 덩어리를 그림으로 같이 외우면 도식형 문제 대응이 빨라진다.",
    ),
]

COMPARE_TABLE_ROWS = [
    ("동기이론", "매슬로우·허즈버그·브룸·아담스", "무엇이 사람을 움직이는지, 욕구/기대/공정의 초점을 비교"),
    ("전략유형", "원가우위·차별화·집중화", "경쟁우위의 원천이 비용인지 가치인지 먼저 구분"),
    ("STP와 4P", "시장 선택 단계 / 실행 수단 단계", "전략과 실행을 섞지 않는 것이 핵심"),
    ("재무제표", "재무상태표·손익계산서·현금흐름표·자본변동표", "각 표가 보여 주는 대상이 다르다"),
    ("투자안 평가", "NPV·IRR·회수기간", "채택 기준과 장단점을 함께 비교"),
    ("운영관리", "재고·품질·공정·혁신", "계산형과 개념형이 섞여 나오는 파트라 큰 분류가 중요"),
]


@dataclass
class ManagementQuestion:
    number: int
    section: str
    statement: str
    answer: str
    basis: str
    explanation: str
    source: str


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.stem}_backup_before_enhance_{timestamp}{path.suffix}")
    backup.write_bytes(path.read_bytes())
    return backup


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = text.replace("•", "·").replace("ㆍ", "·")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip()


def needs_spacing(text: str) -> bool:
    compact = re.sub(r"[^가-힣A-Za-z0-9]", "", text)
    if " " in text:
        return False
    return len(compact) >= 14


def space_text(text: str) -> str:
    updated = normalize_text(text)
    if not updated:
        return updated
    if needs_spacing(updated):
        updated = KIWI.space(updated)
    for before, after in DIRECT_REPLACEMENTS.items():
        updated = updated.replace(before, after)
    for pattern, replacement in REGEX_REPLACEMENTS:
        updated = re.sub(pattern, replacement, updated)
    updated = re.sub(r"\s+([.,;:])", r"\1", updated)
    updated = re.sub(r"\(\s+", "(", updated)
    updated = re.sub(r"\s+\)", ")", updated)
    updated = re.sub(r"\s{2,}", " ", updated)
    return updated.strip()


def parse_existing_doc(path: Path) -> list[ManagementQuestion]:
    doc = Document(str(path))
    questions: list[ManagementQuestion] = []
    section = ""
    current: dict[str, str | int] | None = None
    in_body = False

    def flush() -> None:
        nonlocal current
        if not current:
            return
        questions.append(
            ManagementQuestion(
                number=int(current["number"]),
                section=str(current["section"]),
                statement=space_text(str(current["statement"])),
                answer=str(current.get("answer", "")).strip(),
                basis=space_text(str(current.get("basis", "")).strip()),
                explanation=space_text(str(current.get("explanation", "")).strip()),
                source=normalize_text(str(current.get("source", "")).strip()),
            )
        )
        current = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if not in_body:
            if "OX 본문" in text:
                in_body = True
            continue

        if text in SECTION_ORDER:
            flush()
            section = text
            continue

        if current is None and section and not re.match(r"^\d+\.\s*", text):
            continue

        match = re.match(r"^(\d+)\.\s*(.*)$", text)
        if match:
            flush()
            current = {
                "number": int(match.group(1)),
                "section": section,
                "statement": match.group(2).strip(),
            }
            continue

        if not current:
            continue
        if text.startswith("● 정답:") or text.startswith("정답:"):
            current["answer"] = text.split(":", 1)[1].strip()
        elif text.startswith("근거:"):
            current["basis"] = text.split(":", 1)[1].strip()
        elif text.startswith("해설:"):
            current["explanation"] = text.split(":", 1)[1].strip()
        elif text.startswith("출처:"):
            current["source"] = text.split(":", 1)[1].strip()

    flush()
    return questions


def extract_quoted_statements(text: str) -> list[str]:
    return [space_text(m) for m in re.findall(r'"([^"]+)"', text)]


def extract_basis_focus(basis: str) -> str:
    text = space_text(basis)
    match = re.search(r"\(([^()]+)\)", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"(제\d+조(?:의\d+)?(?:\s*제\d+항)?)", text)
    if match:
        return match.group(1).replace("  ", " ").strip()
    return ""


def extract_statement_focus(statement: str) -> str:
    words: list[str] = []
    for token in KIWI.tokenize(space_text(statement)):
        if not token.tag.startswith("NN"):
            continue
        word = token.form.strip()
        if len(word) <= 1 or word in FOCUS_STOPWORDS or word in words:
            continue
        words.append(word)
        if len(words) == 3:
            break
    return "·".join(words)


def select_focus(basis: str, statement: str) -> str:
    basis_focus = extract_basis_focus(basis)
    if basis_focus and not re.fullmatch(r"제\d+조(?:의\d+)?(?:\s*제\d+항)?", basis_focus):
        return basis_focus
    statement_focus = extract_statement_focus(statement)
    return statement_focus or basis_focus


def build_focus_key(focus: str, fallback: str) -> str:
    if focus:
        return f"이 문제는 '{focus}' 기준 개념을 정확히 기억하는지가 핵심이다."
    return fallback


def build_focus_example(focus: str, fallback: str) -> str:
    if focus:
        return f"예를 들어 '{focus}' 문제는 개념 이름을 먼저 확인한 뒤, 정의·구성요소·적용 범위를 순서대로 떠올리면 훨씬 정리가 쉽다."
    return fallback


def build_explanation(q: ManagementQuestion) -> str:
    text_for_match = normalize_text(q.statement)
    guide = None
    for pattern, candidate in ISSUE_SPECIFIC_GUIDES:
        if pattern.search(text_for_match):
            guide = candidate
            break
    if guide is None:
        guide = SECTION_GUIDES.get(q.section, SECTION_GUIDES["기타"])
    focus = select_focus(q.basis, q.statement)
    key = build_focus_key(focus, guide["key"])
    raw = normalize_text(q.explanation)
    for pattern in GENERIC_EXPLANATION_PATTERNS:
        raw = re.sub(pattern, "", raw)
    raw = raw.strip()

    quotes = extract_quoted_statements(raw)
    if q.answer == "O":
        parts = [
            f"정답은 O입니다. 지문이 {q.basis or '해당 개념'} 기준과 일치한다.",
            key,
        ]
        return " ".join(part for part in parts if part).strip()
    else:
        manual = next((text for pattern, text in MANUAL_X_RULES if pattern.search(normalize_text(q.statement))), None)
        if manual:
            core = manual
        elif quotes:
            if len(quotes) == 1:
                core = f"정답은 X입니다. 함께 기억할 올바른 정리는 “{quotes[0]}”이다."
            else:
                core = f"정답은 X입니다. 함께 기억할 올바른 정리는 “{quotes[0]}”, “{quotes[1]}”이다."
        else:
            basis = q.basis or "해당 개념"
            core = f"정답은 X입니다. 지문이 {basis}의 정의·구성요소·적용 범위를 잘못 연결하고 있다."

    return core.strip()


def set_default_font(doc: Document) -> None:
    for style_name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        if style_name not in doc.styles:
            continue
        style = doc.styles[style_name]
        style.font.name = "Malgun Gothic"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
        style.font.size = Pt(10.5 if style_name == "Normal" else 12)


def add_bullets(doc: Document, lines: list[str]) -> None:
    for line in lines:
        doc.add_paragraph(line, style="List Bullet")


def build_doc(questions: list[ManagementQuestion], output_path: Path) -> None:
    doc = Document()
    set_default_font(doc)

    title = doc.add_heading("경영학 OX 통합본", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("2014~2025 기출 반영 / 2026-04-16 기준 심화 보강판").bold = True

    intro = doc.add_paragraph()
    intro.add_run(
        "편집 기준: 경영학개론의 광범위한 출제범위와 2024년 이후 40문항 체계를 반영해, "
        "과목 특징·분야별 출제비중·영역별 전략을 앞부분에 다시 정리했다. 본문 OX는 현재 정제본을 유지하면서 "
        "회독용 단권화 자료로 바로 사용할 수 있게 재배열했다."
    )

    doc.add_heading("Ⅰ. 과목의 특징", level=1)
    add_bullets(
        doc,
        [
            "공인노무사 1차에서 경영학개론은 2010년부터 선택과목으로 채택되었고, 2차의 인사노무관리론·경영조직론과 상당 부분이 연결되는 장점이 있다.",
            "출제범위는 경영학원론, 인적자원관리론, 조직행동론, 경영전략, 마케팅관리론, 생산운영관리론, 재무관리, 회계원리 등을 포함하며, 실전에서는 인사/조직, 재무/회계, 운영관리, 마케팅, 경영일반의 5개 영역으로 보는 편이 효율적이다.",
            "범위가 넓고 지문이 길며 세부 과목까지 깊게 들어가기 때문에 처음 접하는 수험생에게는 만만하지 않은 과목이다.",
            "2024년부터 문항 수가 40문항으로 늘어나면서 재무/회계 비중이 더 높아졌고, 계산에 취약한 수험생에게는 체감 부담이 커졌다.",
            "지엽적인 문제에 끌려가기보다, 반복 출제되는 핵심 개념을 정확히 이해하고 기출문제로 출제 포인트를 잡는 접근이 중요하다.",
        ],
    )

    doc.add_heading("Ⅱ. 최근 10년간 기출문제 분석", level=1)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "분야"
    hdr[1].text = "2016~2023 누계"
    hdr[2].text = "비중"
    hdr[3].text = "2024~2025 누계"
    hdr[4].text = "비중"
    for row_data in SUMMARY_ROWS:
        row = table.add_row().cells
        for idx, val in enumerate(row_data):
            row[idx].text = val

    add_bullets(
        doc,
        [
            "문항 수 확대 이후에도 인사/조직이 가장 높은 비중을 유지하고 있으며, 재무/회계가 거의 같은 수준으로 올라왔다.",
            "운영관리, 경영전략, 마케팅은 예년보다 더 고르게 배분되었지만, 운영관리와 재무/회계의 실제 체감 난도는 여전히 높다.",
            "경영학개론은 최근 타 시험 기출 변형이나 세부 영역 확장 가능성도 높아지고 있어, 2026년에도 전반을 넓게 보는 학습이 유효하다.",
        ],
    )

    doc.add_heading("Ⅲ. 수험전략 및 학습", level=1)
    doc.add_paragraph("1. 인사/조직 분야", style="Heading 2")
    add_bullets(doc, HR_POINTS)
    doc.add_paragraph("2. 재무/회계 분야", style="Heading 2")
    add_bullets(doc, FINANCE_POINTS)
    doc.add_paragraph("3. 마케팅 분야", style="Heading 2")
    add_bullets(doc, MARKETING_POINTS)
    doc.add_paragraph("4. 운영관리 분야", style="Heading 2")
    add_bullets(doc, OPERATIONS_POINTS)
    doc.add_paragraph("5. 경영일반·전략 분야", style="Heading 2")
    add_bullets(doc, GENERAL_POINTS)

    doc.add_heading("Ⅳ. 2026 최종 회독 포인트", level=1)
    add_bullets(doc, FINAL_POINTS)

    doc.add_heading("Ⅴ. 비교해서 외우는 핵심 표", level=1)
    compare_table = doc.add_table(rows=1, cols=3)
    compare_table.style = "Table Grid"
    hdr = compare_table.rows[0].cells
    hdr[0].text = "비교 주제"
    hdr[1].text = "핵심 비교"
    hdr[2].text = "학습 포인트"
    for row_data in COMPARE_TABLE_ROWS:
        row = compare_table.add_row().cells
        for idx, value in enumerate(row_data):
            row[idx].text = value

    doc.add_heading("Ⅵ. 2014~2025 기출 함정 대비 암기 포인트", level=1)
    trap_table = doc.add_table(rows=1, cols=4)
    trap_table.style = "Table Grid"
    hdr = trap_table.rows[0].cells
    hdr[0].text = "혼동 포인트"
    hdr[1].text = "암기 내용"
    hdr[2].text = "두문자"
    hdr[3].text = "암기요령"
    for row_data in TRAP_MEMORY_ROWS:
        row = trap_table.add_row().cells
        for idx, value in enumerate(row_data):
            row[idx].text = value

    doc.add_heading("Ⅶ. OX 본문", level=1)
    grouped: dict[str, list[ManagementQuestion]] = {section: [] for section in SECTION_ORDER}
    for q in questions:
        grouped.setdefault(q.section, []).append(q)

    for section in SECTION_ORDER:
        items = grouped.get(section, [])
        if not items:
            continue
        doc.add_paragraph(section, style="Heading 2")
        doc.add_paragraph(SECTION_NOTES[section])
        for q in items:
            doc.add_paragraph(f"{q.number}. {q.statement}")
            doc.add_paragraph(f"● 정답: {q.answer}")
            doc.add_paragraph(f"근거: {q.basis}")
            doc.add_paragraph(f"해설: {build_explanation(q)}")
            if q.source:
                doc.add_paragraph(f"출처: {q.source}")

    doc.add_heading("Ⅷ. 마무리 메모", level=1)
    add_bullets(
        doc,
        [
            "경영학개론은 70~80점 정도를 목표로 잡고, 항상 반복 출제되는 영역을 안정적으로 확보하는 전략이 가장 현실적이다.",
            "재무/회계처럼 부담이 큰 파트는 빈출 유형 중심으로, 인사/조직과 전략은 2차 연계까지 염두에 두고 깊게 보는 식으로 영역별 시간 배분을 달리하는 편이 좋다.",
            "최근 타 시험 기출문제와 기존 노무사 기출을 함께 보면 지엽적 변형에도 훨씬 덜 흔들린다.",
        ],
    )

    doc.save(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx_path", nargs="?", default=str(DEFAULT_INPUT))
    args = parser.parse_args()

    output_path = Path(args.docx_path).expanduser()
    if not output_path.exists():
        raise SystemExit(f"입력 파일이 없습니다: {output_path}")

    backup = backup_file(output_path)
    questions = parse_existing_doc(output_path)
    build_doc(questions, output_path)
    print(f"backup={backup}")
    print(f"output={output_path}")
    print(f"questions={len(questions)}")


if __name__ == "__main__":
    main()
