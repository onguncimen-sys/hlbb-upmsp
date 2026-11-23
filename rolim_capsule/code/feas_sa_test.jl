#=
FEASIBILITY HARNESS (SA nis-genisletmesi dogrulamasi - 2. ayak).
Equivalence pure-cekirdegin BOZULMADIGINI kanitladi; bu test elig+ready guard'larinin
NIS-MODDA GERCEKTEN uygulandigini kanitlar: kisitli eligibility + nonzero ready ile kosup
HER iterasyonda sol'u denetler:
  (a) elig_viol : uygunsuz makineye atanmis is sayisi (0 OLMALI)
  (b) span_mismatch : MachineSpan != r_l + is-yuku olan makine sayisi (ready tam-bir-kez, 0 OLMALI)
  (c) cov_viol : tam olarak 1 kez atanmamis is sayisi (0 OLMALI)   <-- 2026-07-31 EKLENDI

KAPSAM NOTU: Main_SA'da cozumu YAPISAL olarak degistiren yalniz iki sey vardir --
InitialSolution (SA.jl:579) ve LocalSearch (SA.jl:612). Geri kalani UpdateSolution
(kopyalama), kabul karari ve sicaklik guncellemesidir; cizelgeye dokunmaz. Bu test o iki
operatoru de kapsar, LocalSearch'u her cagrisindan sonra denetler -> operator kumesinin %100'u.

BOYUT: varsayilan m=4,n=30 (regresyon; onceki sonuclarla kiyaslanabilir kalsin).
Benchmark olceginde de kosulabilsin diye parametrik.

Kullanim: julia feas_sa_test.jl <SA.jl-yolu> [m] [n] [iters]
  -> stdout: FEAS_RESULT elig_viol=<N> span_mismatch=<N> cov_viol=<N> checks=<N> m=<m> n=<n>
=#
include(ARGS[1])          # extended SA.jl (nis-modda)
using Random

# ---- boyut (varsayilan: orijinal regresyon instance'i) ----
const M_ = Int8(length(ARGS) >= 2 ? parse(Int, ARGS[2]) : 4)
const N_ = Int16(length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 30)
const ITERS = length(ARGS) >= 4 ? parse(Int, ARGS[4]) : 20000

# ---- nis instance: kisitli eligibility + nonzero ready ----
Random.seed!(2024)
p = Int16.(rand(1:99, Int(M_), Int(N_)))
S = Matrix{Int16}[ Int16.([i == j ? 0 : rand(1:99) for i in 1:Int(N_), j in 1:Int(N_)]) for _ in 1:Int(M_) ]

# ready-time r_l (nonzero, farkli) — guard tetiklenmeli
r = Int32[Int32(rand(0:200)) for _ in 1:Int(M_)]

# eligibility M[j][l] in {0,1}, ~%50, her isin >=1 uygun makinesi (feasibility garantisi)
function make_elig(n::Int, m::Int)
    M = Vector{Vector{Int}}(undef, n)
    for j in 1:n
        row = Int[rand() < 0.5 ? 1 : 0 for _ in 1:m]
        if sum(row) == 0; row[rand(1:m)] = 1; end   # at least one eligible machine
        M[j] = row
    end
    return M
end
M = make_elig(Int(N_), Int(M_))

_set_niche!(Int(M_), Int(N_), r, M)   # nis-mod AKTIF (r,M != nothing -> guard'lar canli)

# ---- KAPSAMA: her is TAM 1 kez mi? (kayip / ciftlenmis / gecersiz indeks) ----
function coverage_viol(sol, m::Int, n::Int)
    cnt = zeros(Int, n)
    bad = 0
    for l in 1:m, job in sol[l]
        j = Int(job)
        if j < 1 || j > n
            bad += 1                                  # gecersiz is indeksi
        else
            cnt[j] += 1
        end
    end
    return bad + count(c -> c != 1, cnt)               # !=1 olan her is bir ihlal
end

# ---- denetim: sol elig + ready-tutarliligi + kapsama ----
function check(sol, M, r, p, S, m, n)
    ve = 0
    for l in 1:Int(m), job in sol[l]
        if M[job][l] != 1; ve += 1; end                 # uygunsuz atama
    end
    sm = 0
    for l in 1:Int(m)
        work::Int = 0                                    # ready HARIC is-yuku
        route = sol[l]
        for i in eachindex(route)
            work += p[l, route[i]]
            if i != length(route); work += S[l][route[i], route[i+1]]; end
        end
        ms = Int(MachineSpan(Int8(l), p, S, sol))
        if ms != Int(r[l]) + work; sm += 1; end          # ready tam-bir-kez mi?
    end
    cv = coverage_viol(sol, Int(m), Int(n))
    return ve, sm, cv
end

function run_feas(m, n, p, S, M, r, iters)
    Random.seed!(7)
    sol = InitialSolution(m, n)
    MS = zeros(Int32, Int(m))
    for i in 1:Int(m); MS[i] = MachineSpan(Int8(i), p, S, sol); end
    tot_e = 0; tot_s = 0; tot_c = 0; checks = 0
    ve, sm, cv = check(sol, M, r, p, S, m, n)
    tot_e += ve; tot_s += sm; tot_c += cv; checks += 1
    for it in 1:iters
        LocalSearch(sol, MS, m, n, p, S)
        ve, sm, cv = check(sol, M, r, p, S, m, n)        # HER iterasyon (airtight)
        tot_e += ve; tot_s += sm; tot_c += cv; checks += 1
    end
    return tot_e, tot_s, tot_c, checks
end

ve, sm, cv, ck = run_feas(M_, N_, p, S, M, r, ITERS)
println("FEAS_RESULT elig_viol=$ve span_mismatch=$sm cov_viol=$cv checks=$ck m=$(Int(M_)) n=$(Int(N_))")
