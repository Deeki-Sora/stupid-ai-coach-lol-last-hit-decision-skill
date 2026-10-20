# LOL短时补兵决策评估框架（精简版）

## 摘要

本文给出一个用于复盘和短时决策的离散事件模型。分析窗口从 (t_0) 到 (T)，通常覆盖一波兵线或连续的 20–30 秒。模型以一方英雄为中心，记录双方状态、可执行动作、兵线事件和共同终点收益。评价先筛除不可执行动作，再计算动作质量，最后比较双方在经验、金币和可恢复状态上的相对结果。

## 1. 研究对象与窗口

设分析主体为 (A)，对手为 (B)。

状态信念为

\[
\Omega_t=(X_t,\mathcal E_t,\Theta_t),\quad X_t=(g_t,x_t,h_t,m_t,c_t,s_t,p_t)
\]

其中 (g,x,h,m,c,s,p) 分别表示金币、经验、生命资源、法力或能量、冷却状态、召唤师技能与消耗品、位置；(mathcal E_t) 为待处理事件，(Theta_t) 为版本、英雄、装备和符文参数。窗口只评价 (t_0le tle T) 内的行为，不外推整场比赛。

## 2. 状态与事件推进

事件包括普攻、技能、移动、受击、兵死亡、资源到账和冷却结束。状态更新写为

\[
x_{t+\Delta t}=F(x_t,a_t,e_t;\Theta_t),\quad e_t\sim P(\cdot\mid x_t,a_t)
\]

动作占用前摇、命中、后摇和移动时间；事件按时间顺序推进。事件不可观测时保留分支概率，不以零收益替代未知结果。

## 3. 补刀机会与合法性

对小兵 (i) 和动作类型 (r)，补刀窗口为

\[
W_i^r=\{t:0<h_i(t^-)\le d_i^r(x_t)\}
\]

可执行动作集合为

\[
C_i^r=\{a:\operatorname{Ready}(a)\land\operatorname{Reach}(a,i)\land t_{\rm hit}(a,i)\in W_i^r\}
\]

统一合法性门为

\[
E(a\mid\Omega_t)=\mathbf1\{\text{version, range, cooldown, control, resource, occupation, deadline}\}
\]

若动作被控制、已有动作不可取消、资源不足或不能在死亡截止时间前命中，则 (E=0)。非法动作记录其观测结果，但不进入合法动作质量平均值。

## 4. 联合调度与自由时间

多个目标的动作序列 (pi=(a_1,ldots,a_n)) 必须满足

\[
t_{k+1}\ge t_k+\tau_k,\quad t_k\le t_i^{\rm death},\quad \pi=(a_1,\ldots,a_n)
\]

其中 (	au_k) 为动作占用时间。保持小兵死亡顺序和补刀窗口的剩余时间后，主体的自由时间定义为

\[
F_A(\pi)=\{t\in[t_0,T]:\pi\text{ preserves the scheduled minion deaths and hit windows}\}
\]

自由时间中的消耗动作只有在不破坏既定补刀时序时才计入压力层。

## 5. 条件质量层

动作质量由合法性门和可用质量层共同决定：

\[
Q(a)=E(a\mid\Omega_t)\frac{\sum_{j\in J(a)}w_jq_j(a)}{\sum_{j\in J(a)}w_j},\quad q_j\in[-1,1]
\]

\[
\operatorname{cov}(a)=\frac{\sum_{j\in J(a)}w_j}{\sum_{j\in J_{\rm all}}w_j}
\]

缺失层从分母排除，并报告覆盖度。常用层如下：

\[
q_{\rm time}=\operatorname{clip}\left(2\frac{\sigma_t}{\sigma_{\max}}-1,-1,1\right)
\]

\[
R_{\rm eff}(a)=\begin{cases}R(a)&\text{if available and controllable}\\0&\text{otherwise}\end{cases}
\]

\[
q_{\rm edge}=2\operatorname{clip}\left(1-\frac{|d-R_{\rm eff}|}{\delta},0,1\right)-1
\]

其中 (sigma_t) 为命中或死亡截止时间余量，(d) 为观测距离，(delta) 为边缘容差。有效范围为零时，不把不可用技能或普攻误判为距离优势。普攻层、施法层和边缘层按事件可用性依次计算；技能命中只影响相应分支和终点状态。

## 6. 终点相对收益

窗口终点比较双方的增量：

\[
\Delta z_k=(z_{A,k}(T)-z_{A,k}(t_0))-(z_{B,k}(T)-z_{B,k}(t_0))
\]

其中 (z_k) 可为金币、经验、生命、法力或能量、冷却储备和召唤师技能储备。可恢复状态按窗口终点的可恢复量计算，而不是直接比较当前百分比：

\[
r_k=\frac{\min\{M_k,z_k(T)+\rho_k(T)\}-z_k(T)}{M_k}
\]

\[
V_{\rm end}=\sum_k w_k\widetilde{\Delta z_k},\quad \sum_k w_k=1
\]

(widetilde{Delta z_k}) 为按量纲和方向归一化后的相对增量。金币和经验增加为正；生命、法力、冷却和召唤师技能则按可用储备增加为正、消耗为负。终点收益不重复计算已经在补刀收益中计入的事件。

## 7. 概率分支与短时决策

对候选动作 (a) 的分支价值为

\[
V(a)=\sum_b p_bV_b-\lambda\operatorname{CVaR}_{\alpha}(-V_b)+\nu\operatorname{VOI}(a)-\kappa C_{\rm exec}(a)
\]

其中 (p_b) 为命中、未命中、兵死亡顺序和技能触发等分支概率。风险只改变候选动作的分支价值，不直接扣除行为质量。信息动作仅在其预期信息价值超过截止时间损失时保留。

## 8. 分项评分

理论补刀上限为 (N_{\rm cs}^{\max}) 时，补刀分为

\[
S_{\rm cs}=100\min\left(1,\frac{N_{\rm cs}}{N_{\rm cs}^{\max}}\right)
\]

策略分由资源取得、经验取得、补刀间隔压力和终点相对状态组成：

\[
S_{\rm strategy}=w_{\rm cs}S_{\rm cs}+w_{\rm xp}S_{\rm xp}+w_{\rm pressure}S_{\rm pressure}+w_{\rm end}S_{\rm end},\quad \sum w=1
\]

执行分为可用质量层的归一化结果：

\[
S_{\rm execution}=100\frac{Q+1}{2}
\]

最终分保持策略与执行各占一半：

\[
S_{\rm total}=0.5S_{\rm strategy}+0.5S_{\rm execution}
\]

结果同时报告分项分数、覆盖度、合法性、终点向量和不确定区间。总分不能替代分项解释。

## 9. 输出格式与使用边界

一次动作或一次事件链至少输出：

```json
{
  "eligible": true,
  "layers": {"timing": 0.72, "conversion": 0.64, "endpoint": 0.81},
  "coverage": 0.91,
  "endpoint_vector": {},
  "violations": [],
  "interval": [61.0, 74.0]
}
```

英雄、装备、符文和小兵的版本数据属于输入参数。特殊机制可以用观测到的触发状态、层数、冷却和命中概率输入；模型不要求为每个英雄编写独立决策规则。工作台、视频采样和像素测量属于数据准备工具，不改变本模型的计算定义。

## 10. 复盘解释

报告应指出：哪一个合法窗口被利用或错过；错过的时间、距离或攻击相位余量；补刀时序是否改变；对手是否实际承担生命、法力、冷却或召唤师技能成本；以及这些变化如何进入终点相对收益。没有证据的行为保持为概率分支，并给出区间而不是单一确定结论。
