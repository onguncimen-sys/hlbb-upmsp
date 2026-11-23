#=
FEASIBILITY HARNESS (GA nis-genisletmesi). Kisitli elig + nonzero ready.
Her nesilde O1/O2 (crossover+LS+mutasyon sonrasi) denetlenir:
  elig_viol (0 olmali)     : uygunsuz makineye atanmis is
  span_mismatch (0 olmali) : MachineSpan != r_l + is-yuku (ready tam-bir-kez)
  cov_viol (0 olmali)      : tam olarak 1 kez atanmamis is   <-- 2026-07-31 EKLENDI

BOYUT: varsayilan m=4,n=30 (regresyon). Benchmark olceginde de kosulabilsin diye parametrik.
Kullanim: julia feas_ga_test.jl <GA.jl-yolu> [m] [n] [iters]
  -> FEAS_RESULT elig_viol=N span_mismatch=N cov_viol=N checks=N m=<m> n=<n>
=#
include(ARGS[1])
using Random

const M_ = Int8(length(ARGS) >= 2 ? parse(Int, ARGS[2]) : 4)
const N_ = Int16(length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 30)
const ITERS = length(ARGS) >= 4 ? parse(Int, ARGS[4]) : 300

Random.seed!(2024)
p = Int16.(rand(1:99, Int(M_), Int(N_)))
S = Matrix{Int16}[ Int16.([i == j ? 0 : rand(1:99) for i in 1:Int(N_), j in 1:Int(N_)]) for _ in 1:Int(M_) ]
r = Int32[Int32(rand(0:200)) for _ in 1:Int(M_)]

function make_elig(n::Int, m::Int)
    M = Vector{Vector{Int}}(undef, n)
    for j in 1:n
        row = Int[rand() < 0.5 ? 1 : 0 for _ in 1:m]
        if sum(row) == 0; row[rand(1:m)] = 1; end
        M[j] = row
    end
    return M
end
M = make_elig(Int(N_), Int(M_))
_set_niche!(Int(M_), Int(N_), r, M)

# KAPSAMA: her is TAM 1 kez mi? (kayip / ciftlenmis / gecersiz indeks)
function coverage_viol(Sol, m::Int, n::Int)
    cnt = zeros(Int, n)
    bad = 0
    for l in 1:m, job in Sol[l]
        j = Int(job)
        if j < 1 || j > n; bad += 1; else; cnt[j] += 1; end
    end
    return bad + count(c -> c != 1, cnt)
end

function check(Sol, M, r, p, S, m, n)
    ve = 0
    for l in 1:Int(m), job in Sol[l]
        if M[job][l] != 1; ve += 1; end
    end
    sm = 0
    for l in 1:Int(m)
        work::Int = 0
        route = Sol[l]
        for i in eachindex(route)
            work += p[l, route[i]]
            if i != length(route); work += S[l][route[i], route[i+1]]; end
        end
        ms = Int(MachineSpan(Int8(l), p, S, Sol))
        if ms != Int(r[l]) + work; sm += 1; end
    end
    cv = coverage_viol(Sol, Int(m), Int(n))
    return ve, sm, cv
end

function run_feas(m, n, p, S, M, r, iters)
    Random.seed!(7)
    Psize = Int8(80); Pc = Float16(0.5); Pm = Float16(0.5)
    Pls = Float16(1.0); Pressure = Int8(10)
    POP = Init_Pop(Psize, m, n, p, S)
    tot_e = 0; tot_s = 0; tot_c = 0; checks = 0
    for ind in POP                                   # baslangic populasyonu (MI_heuristic)
        ve, sm, cv = check(ind.Sol, M, r, p, S, m, n)
        tot_e += ve; tot_s += sm; tot_c += cv; checks += 1
    end
    for it in 1:iters
        O1, O2, _ = CrossOver(POP, Pc, Pressure, Psize, m, p, S)
        IMI_LS(Pls, m, p, S, O1)
        IMI_LS(Pls, m, p, S, O2)
        Mutation(O1, O2, Pm, m, p, S)
        for ind in (O1, O2)
            ve, sm, cv = check(ind.Sol, M, r, p, S, m, n)
            tot_e += ve; tot_s += sm; tot_c += cv; checks += 1
        end
        UpdatePopulation(O1, POP, Psize)
        UpdatePopulation(O2, POP, Psize)
    end
    return tot_e, tot_s, tot_c, checks
end

ve, sm, cv, ck = run_feas(M_, N_, p, S, M, r, ITERS)
println("FEAS_RESULT elig_viol=$ve span_mismatch=$sm cov_viol=$cv checks=$ck m=$(Int(M_)) n=$(Int(N_))")
